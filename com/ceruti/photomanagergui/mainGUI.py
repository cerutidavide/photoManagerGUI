import datetime
import hashlib
import logging
import os
import pathlib
import re
import shutil
import time
import wx
import wx.dataview
from PIL import Image
from PIL import UnidentifiedImageError
from PIL.ExifTags import TAGS
from PIL.TiffTags import TAGS
from send2trash import send2trash
import exiftool
from datetime import datetime
from exiftool.exceptions import ExifToolException
# NB per cambiare tra pc aziendale e di casa basta commentre/scommentare dove va in errore
# NB pip install --proxy http://user:password@proxy.dominio.it:porta wxPython



# TODO PRINCIPALE: lista task minimali per costruire il nuovo archivio
# 1. impostazione/fix data per foto "sbagliate" --> da fare correggere conteggio nb controllare quali sono i campi effettivi in cui si salvano le date corrette (verificare tag exif e anche tag file e check cosa vede il sistema operativo)
# TODO FORMATTAZIONE LOG
# TODO gestione immagini non riconosciute con Exitool
# TODO valutare "con e senza exif tool"
# TODO conteggio file e cartelle in check duplicati archivio
# TODO conteggio errori copia
# TODO conteggio Immagini non identificate e lista dei file non identificati da (eventualemente) pulire
# TODO LOG SU FILE
# TODO CONTROLLO PERMESSI
# TODO sistemare pulsanti e barre di avanzamento
# TODO riorganizzare interfaccia grafica
# TODO EXIF SET GPS DATA ORA
# TODO check VERO DUPLICATI (con un dict, direttamente sull'archivio e fare anche statistiche sull'archivio)
# TODO valutare database per statistiche
# TODO valutare refactor "a oggetti" con vari moduli
# TODO Impacchettare appliczione
# TODO valutare/verificare multiplatform


def loadFileExtensionList(self, filepath="/tmp/", extensionList=[], firstcall=True):
    if firstcall is True:
        extensionList = []
    try:
        for file in os.listdir(filepath):
            if os.path.isdir(filepath + "/" + file):
                loadFileExtensionList(self, filepath + "/" + file, extensionList, False)
                pass
            else:
                ext = os.path.splitext(filepath + "/" + file)
                if ext[1] != "":
                    if ext[1] not in extensionList:
                        extensionList.append(ext[1])
                        logger.debug("Aggiunta " + ext[1] + " alla lista delle estensioni")
                        self.gauge.SetValue(self.gauge.GetValue() + 1)
                        if self.gauge.GetValue() >= self.gauge.GetRange():
                            self.gauge.SetValue(0)
    except Exception as e:
        print(e)
    return extensionList


def CheckAndLoadProperties(workingdir='c:\\Users\\Davide\\PycharmProjects\\photoManagerGUI',
                           filenameGlob="default.props", filenameMstr=".masterrepository.conf"):
    myHashGlob = {}
    myHashGlob['fileconfprincipale'] = filenameGlob
    logger.debug("<<Parametro impostato #file_di_configurazione_principale# " + os.path.join(workingdir, filenameGlob))
    myHashGlob['masterrepositoryconf'] = filenameMstr
    logger.debug("<<Parametro impostato #masterrepositoryconf# " + filenameMstr)
    with open(os.path.join(workingdir, filenameGlob), encoding="utf-8") as f:
        for line in f.readlines():
            # print(line)
            match = re.search('^masterrepository=(.*)', line)
            # print(match)
            if match:
                myHashGlob['masterrepository'] = match[1]
                logger.debug("<<Parametro letto nel file #masterrepository# " + str(match[1]))
            match = re.search('^workingfolder=(.*)', line)
            if match:
                myHashGlob['workingfolder'] = match[1]
                logger.debug("<<Parametro letto nel file #workingfolder# " + str(match[1]))
            match = re.search('^importfilelist=(.*)', line)
            if match:
                myHashGlob['importfilelist'] = match[1]
                logger.debug("<<Parametro letto nel file #importfilelist# " + str(match[1]) + "\n")
            match = re.search('^masterrepository_bin=(.*)', line)
            if match:
                myHashGlob['masterrepository_bin'] = match[1]
                logger.debug("<<Parametro letto nel file #masterrepository_bin# " + str(match[1]) + "\n")

    return myHashGlob


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title, *args, **kw):
        super().__init__(*args, **kw)
        wx.Panel.__init__(self, parent, title=title, size=(725, 700))
        max_gauge_size = 700
        self.checkRunning = True

        if(os.path.exists("C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master")):
            self.basePath="C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master"
        if(os.path.exists("C:\\Users\\Davide\\PhotoManager")):
            self.basePath="C:\\Users\\Davide\\PhotoManager"
        self.baseFile = "default.props"
        logger.info("###PARAMETRO FILE BASE### " + self.basePath + "\\" + self.baseFile + "\n")
        logger.info("###MODIFICARE basePath PER AZIENDALE: C:\\Users\\Davide\\PhotoManager ###")
        logger.info("###MODIFICARE basePath PER PC CASA:   C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master ###\n")
        self.globpropsHash = CheckAndLoadProperties(self.basePath, self.baseFile, ".masterrepository.conf")

        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))
        self.globpropsHash['f_copia'] = dict()
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))
        self.globpropsHash['f_checkarchivio'] = dict()
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))
        self.globpropsHash['f_listaestensioni'] = dict()
        self.globpropsHash['f_copia']['copied'] = []
        self.globpropsHash['f_copia']['skipped'] = []
        self.globpropsHash['f_copia']['tot_files'] = []
        self.globpropsHash['f_copia']['tot_dirs'] = []
        
        self.globpropsHash['f_fixdate'] = dict()
        self.globpropsHash['f_fixdate']['fixed'] = []
        self.globpropsHash['f_fixdate']['skipped'] = []
        self.globpropsHash['f_fixdate']['tot_files'] = []
        self.globpropsHash['f_fixdate']['tot_dirs'] = []

        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))

        self.importDirFileExtensions = {}
        self.importMd5fileHash = {}
        self.duplicatedFilesDict = {}
        self.duplicatedFilesListValues=[]
        self.skippedfileHash = {}
        self.loggingDict = {}
        self.importDirError = 0
        self.copymode = 0

        self.gauge = wx.Gauge(self, pos=(5, 640), size=(max_gauge_size, -1))
        self.gauge.SetRange(max_gauge_size)
        self.gauge.SetValue(0)

        self.workingDirList = wx.GenericDirCtrl(self, pos=(5, 30), size=(345, 230), style=wx.DIRCTRL_DIR_ONLY)
        if 'workingfolder' not in self.globpropsHash.keys():
            self.workingDirList.SetPath("c:\\temp")
            self.workingDirList.SelectPath("c:\\temp", select=True)
            self.globpropsHash['workingfolder']="C:\\temp"
        else:
            self.workingDirList.SetPath(self.globpropsHash['workingfolder'])
            self.workingDirList.SelectPath(self.globpropsHash['workingfolder'], select=True)
        self.workingDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaWorkingDir)



        self.treeTitle = wx.StaticText(self, label="Scegliere Cartella di lavoro per le azioni sulla destra:", pos=(5, 5), size=(345, 25))

        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),
                                          pos=(360, 400))

        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file Cartella Selezionata",
                                                    pos=(360, 30),size=(345,-1))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)
        self.avviaCopiaFile = wx.Button(self, label="Avvia Import In Archivio Master", pos=(360, 90),size=(345,-1))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.modoCopia = wx.RadioBox(self, label="Azione Su File Da Importare:", majorDimension=3,
                                     pos=(360, 120), size=(345, -1),
                                     choices=["nessuna azione", "cestino archivio", "cestino windows"])
        self.avviaCheckArchivio = wx.Button(self, label="Avvia Controllo Duplicati Cartella Selezionata", pos=(360, 55),size=(345,-1))
        self.avviaCheckArchivio.Bind(wx.EVT_BUTTON, self.AvviaCheckArchivio)

        self.avviaFixDateTime = wx.Button(self, label="Avvia Fix Orario Cartella Selezionata", pos=(360, 180),size=(345,-1))
        self.avviaFixDateTime.Bind(wx.EVT_BUTTON, self.AvviaFixDateTime)
        self.modoFixData = wx.RadioBox(self, label="Attraversare Sotto Cartelle Sì/No", majorDimension=2,
                                     pos=(360, 210), size=(345, -1),
                                     choices=["Sì", "No"])


        self.esci = wx.Button(self, label="ESCI", pos=(360, 280), size=(345, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)

        self.outputWindow = wx.TextCtrl(self, pos=(5, 280), size=(345, 300),style=wx.TE_MULTILINE)
        

        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0, 'tot_dirs':0, 'duplicated_files':0}
        
        self.SetFocus()
        self.Center()
        self.Show(True)
    def CleanConfigFunction(self):
        #potrei spianare tutti i dict le cui chiavi iniziano per f_
        self.globpropsHash['f_copia']['tot_dirs'].clear()
        self.globpropsHash['f_copia']['tot_files'].clear()
        self.globpropsHash['f_copia']['skipped'].clear()
        self.globpropsHash['f_copia']['copied'].clear()
        self.globpropsHash['f_fixdate']['fixed'].clear()
        self.globpropsHash['f_fixdate']['skipped'].clear()
        self.globpropsHash['f_fixdate']['tot_files'].clear()
        self.globpropsHash['f_fixdate']['tot_dirs'].clear()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())
    def stringFormattedHash(self):
        result = ""
        for k in self.globpropsHash.keys():
            result = result + k + " = " + str(self.globpropsHash[k]) + "\n"
        return result
    def SelezionaWorkingDir(self,evt):        
        if self.workingDirList.GetPath():
            self.globpropsHash['workingfolder'] = self.workingDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())
    def AvviaCaricaEstensioni(self, evt):
        logger.debug("**********  %s ",self.globpropsHash['workingfolder'])
        messaggioEstensioni = str(loadFileExtensionList(self, self.globpropsHash['workingfolder'], True))
        messaggioFolderImport =self.globpropsHash['workingfolder']
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension = wx.MessageBox(
            "Nel folder import " + messaggioFolderImport + "\nci sono i seguenti tipi di file: \n" + messaggioEstensioni,
            '', wx.CLOSE)
        logger.info(messaggioEstensioni)
        self.gauge.SetValue(0)

    def Esci(self, evt):
        self.Close()
        pass


    def AvviaFixDateTime(self, evt):        
        self.CleanConfigFunction()
        self.FixDateTime(self.globpropsHash['workingfolder'])                
        self.gauge.SetValue(self.gauge.GetRange())
        logger.info("Dictionary File Da trattare: ")
        outputWindowText=''
        outputWindowText+='<<<< FILE AGGIORNATI: '+str(len(self.globpropsHash['f_fixdate']['fixed']))+' >>>>\n'
        n=1
        for f in self.globpropsHash['f_fixdate']['fixed']:
            logger.info("fixed file >>> %s ",f)
            outputWindowText+=str(n)+'-->'+f+"\n"
            n+=1                                                   
        outputWindowText+='\n<<<< FILE SALTATI: '+str(len(self.globpropsHash['f_fixdate']['skipped']))+' >>>>\n'            
        n=1    
        for s in self.globpropsHash['f_fixdate']['skipped']:
            logger.info("skipped file >>> %s ",s)
            outputWindowText+=str(n)+'-->'+s+"\n"
            n+=1            
        logger.debug("Numero di file aggiornati: %s",len(self.globpropsHash['f_fixdate']['fixed']))
        logger.debug("Numero di file saltati: %s",len(self.globpropsHash['f_fixdate']['skipped']))
        self.outputWindow.SetValue(outputWindowText)
#        okCheck = wx.MessageDialog(self, "File aggiornati: "+str(len(self.globpropsHash['f_fixdate']['fixed']))+" su un totale di "+str(len(self.globpropsHash['f_fixdate']['tot_files']))+"\nFile saltati: "+str(len(self.globpropsHash['f_fixdate']['skipped']))+"\nCartelle percorse: "+str(len(self.globpropsHash['f_fixdate']['tot_dirs'])), style=wx.ICON_INFORMATION, caption="Check Terminato")
#        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()
    def FixDateTime(self, dir="C:\\Users\\c333053\\TestImport", dirrecursion=False):        
        self.fixmode=self.modoFixData.GetSelection()
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_fixdate']['tot_dirs']))
            logger.info("<<<INIZIO CARTELLA %s >>>",dir)
            self.globpropsHash['f_fixdate']['tot_dirs'].append(dir)
            for file in os.scandir(dir):                
                if file.is_dir():                    
                    if self.fixmode==1:
                        logger.debug("DIRECTORY %s <NON ATTRAVERSO LA DIRECTORY> %s",id_log_counter_dir,str(file.path))                                        
                    else:
                        logger.debug("DIRECTORY %s <ATTRAVERSO LA DIRECTORY> %s",id_log_counter_dir,str(file.path))                          
                        self.FixDateTime(file,True)                                      
                else:
                    id_log_counter = str(len(self.globpropsHash['f_fixdate']['tot_files']))
                    logger.info("FILE %s_%s <INIZIO> %s",id_log_counter_dir,id_log_counter, file.path)
                    with exiftool.ExifTool() as et:
                        #Al momento fisso a 7 ore
                        deltaDateTime='00:00:00 07:00:00'
                        exiftoolModDatePar='-ModifyDate+=\"'+deltaDateTime+'\"'
                        exiftoolCreateDatePar='-CreateDate+=\"'+deltaDateTime+'\"'
                        exiftoolOrigDatePar='-DateTimeOriginal+=\"'+deltaDateTime+'\"'
                        logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ",id_log_counter_dir,id_log_counter,exiftoolModDatePar,exiftoolCreateDatePar,exiftoolOrigDatePar)
                        try:
                            et.execute(exiftoolModDatePar,exiftoolCreateDatePar,exiftoolOrigDatePar,file.path)                            
                            srcbckfullfilename=str(file.path)+'_original'                            
                            dstbckfilename=str(file.name)+'_original'                            
                            dstbckfoldername=self.globpropsHash['masterrepository_bin']
                            dstbckfullfilename=dstbckfoldername+'\\'+str(datetime.now()).replace(' ','_').replace(':','_').replace('-','_')+'_'+dstbckfilename                            
                            logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ",id_log_counter_dir,id_log_counter,exiftoolModDatePar,exiftoolCreateDatePar,exiftoolOrigDatePar)
                            logger.debug("FILE %s_%s <STDOUT CMD EXIFTOOL %s > ",id_log_counter_dir,id_log_counter,str(et.last_stdout).replace('\n',''))
                            logger.debug("FILE %s_%s <STDERR CMD EXIFTOOL %s > ",id_log_counter_dir,id_log_counter,str(et.last_stderr))
                            logger.debug("FILE %s_%s <RISULTATO CMD EXIFTOOL %s",id_log_counter_dir,id_log_counter,str(et.last_status))
                            if et.last_status==0 and et.last_stdout.rfind('unchanged')<0 :
                                logger.debug("FILE %s_%s <SRC: %s> <DST: %s>",id_log_counter_dir,id_log_counter,srcbckfullfilename,dstbckfullfilename)
                                self.globpropsHash['f_fixdate']['fixed'].append(str(file.path))        
                                shutil.move(srcbckfullfilename, dstbckfullfilename ,copy_function='copy2')
                            else:
                                logger.error("<<PROBLEMA ESECUZIONE EXIF su file: %s ",file.path) 
                                self.globpropsHash['f_fixdate']['skipped'].append(str(file.path))        
                        except IOError as e:
                            logger.error("<<ERRORE SPOSTAMENTO FILE BACKUP: %s su %s ",srcbckfullfilename,dstbckfullfilename)                            
                        self.globpropsHash['f_fixdate']['tot_files'].append(str(file.path))
            logger.info("<<<FINE CARTELLA>>> <<< %s >>>",dir)    

#   intanto pare che il modify date sia il campo giusto (id 306 di EXIF)
#   IMAGEIO non legge qualcosa mentre exiftool legge tutto--> inutile usare IMAGEIO A REGIME per questa funzione (scrittura EXIF)
#   gestione input --> aggiungere date picker e time picker per adesso delta in ore e fisso
#   esempio >exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2
#   exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2
#
#
#
#

    





    def AvviaCheckArchivio(self, evt):
        self.gauge.SetValue(0)
        self.duplicatedFilesDict.clear()
        self.Errors = 0
        tot_files=0
        self.CheckArchivio(self.globpropsHash['workingfolder'])                
        self.gauge.SetValue(self.gauge.GetRange())
        logger.info("Dictionary File Trovati: ")
        found_duplicate = False
        outputWindowText=''
        for k in self.duplicatedFilesDict.keys():
            logger.info("chiave >>> %s  valore >>> %s",k,self.duplicatedFilesDict[k])
            tot_files+=len(self.duplicatedFilesDict[k])
            if len(self.duplicatedFilesDict[k])>1:
                found_duplicate=True
                outputWindowText+='<<<< INIZIO '+k+'>>>>\n'
                for item in self.duplicatedFilesDict[k]:
                    outputWindowText+='-'+str(self.duplicatedFilesDict[k].index(item)+1)+'>'+item+'\n'
                outputWindowText+='<<<< FINE '+k+'>>>>\n\n'
        if not found_duplicate:
            outputWindowText += 'NON sono stati trovati DUPLICATI\n'
        logger.debug("Numero di file distinti: %s",len(self.duplicatedFilesDict.keys()))
        logger.debug("Numero di file totali: %s",tot_files)
        self.outputWindow.SetValue(outputWindowText)
        if self.Errors == 0:
            okCheck = wx.MessageDialog(self, "FUNZIONE DA COMPLETARE - Check Archivio Terminato\n\nFile distinti trovati: "+str(len(self.duplicatedFilesDict.keys()))+"\n\nFile totali trovati: "+str(tot_files), style=wx.ICON_INFORMATION, caption="Check Terminato")
            okCheck.ShowModal()
        self.gauge.SetValue(0)
    def CheckArchivio(self, dir="C:\\Users\\c333053\\TestImport"):
        id_log_counter_dir = str(self.fileCounter['tot_dirs'])        
        self.gauge.SetValue(self.fileCounter['tot_files'])
        if os.path.exists(dir):
            logger.info("<<< %s >>> %s <<<INIZIO CARTELLA>>>",dir,id_log_counter_dir)
            for file in os.scandir(dir):
                id_log_counter = str(self.fileCounter['tot_files'])
                if file.is_dir():                    
                    logger.debug("FILE %s_%s <è una directory> %s",id_log_counter_dir,id_log_counter,str(file.path))                    
                    self.CheckArchivio(file)
                else:
                    logger.info("FILE %s_%s <INIZIO> %s",id_log_counter_dir,id_log_counter, file.path)
                    logger.debug("FILE %s_%s  <APERTURA FILE> %s",id_log_counter_dir,id_log_counter, str(file.path))
                    with open(file, "rb") as fmd5:
                        md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()
                        logger.debug("FILE %s_%s <md5 calcolato> %s",id_log_counter_dir,id_log_counter,md5filename)
                        if md5filename not in self.duplicatedFilesDict:
                            self.duplicatedFilesDict[md5filename]=[file.path]                            
                            logger.debug("FILE %s_%s <INSERIMENTO NUOVO> chiave: %s valore %s",id_log_counter_dir,id_log_counter,md5filename,str(self.duplicatedFilesDict[md5filename]))
                        else:
                            listvalue=self.duplicatedFilesDict[md5filename]
                            listvalue.append(file.path)
                            logger.debug('FILE %s_%s <AGGIUNTA FILE DUPLICATO>: %s , Nuovo valore lista file per chiave: %s',id_log_counter_dir,id_log_counter,file.path,listvalue)
                            self.duplicatedFilesDict[md5filename]=listvalue
                            logger.debug('FILE %s_%s <AGGIUNTA FILE DUPLICATO> <k,v> chiave: %s, valore: %s',id_log_counter_dir,id_log_counter,md5filename, self.duplicatedFilesDict[md5filename])                                                    
                        fmd5.close()
                        logger.debug("FILE %s_%s <CHIUSURA FILE> %s",id_log_counter_dir,id_log_counter, str(file.path))
                    self.fileCounter['tot_files']+=1
                    self.gauge.SetValue(self.fileCounter['tot_files'])
            logger.info("<<< %s >>> %s <<<FINE CARTELLA>>>",str(dir),id_log_counter_dir)
    def AvviaCopiaFile(self, evt):
        self.CleanConfigFunction()
        logger.debug("###PARAMETRI DI CONFIGURAZIONE PRIMA DELL INIZIO COPIA###  \n" + str(self.globpropsHash))
        self.importDirError = 0
        self.CopiaFile(self.globpropsHash['workingfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))
        if self.importDirError == 0:
            okMD5 = wx.MessageDialog(self, "Import File Terminato\n\n" + "File copiati: " + str(
                len(self.globpropsHash['f_copia']['copied'])) + "\nFile saltati: " + str(
                len(self.globpropsHash['f_copia']['skipped'])) + "\nFile totali: " + str(len(self.globpropsHash['f_copia']['tot_files'])),
                                     style=wx.ICON_INFORMATION, caption="Copia Terminata")
            okMD5.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()


    def CopiaFile(self, dir="C:\\Users\\c333053\\TestImport"):
        id_log_counter_dir =len(self.globpropsHash['f_copia']['tot_dirs'])
        if os.path.exists(dir):
            logger.info("<<<"+str(dir)+">>> "+str(id_log_counter_dir)+" <<<INIZIO CARTELLA>>>")
            for file in os.scandir(dir):
                id_log_counter_file =len(self.globpropsHash['f_copia']['tot_files'])
                if file.is_dir():
                    self.globpropsHash['f_copia']['tot_dirs'].append(file.path)
                    logger.debug("FILE " + str(id_log_counter_dir) + "_" + str(
                        id_log_counter_file) + " <è una directory> " + file.path)
                    self.CopiaFile(file)
                else:
                    logger.info("FILE " + str(id_log_counter_dir)+"_"+str(id_log_counter_file) + " <INIZIO> " + str(file.path))
                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <è un file...> " + str(file.path)+" LO APRO")
                    self.globpropsHash['f_copia']['tot_files'].append(file.path)
                    with open(file, "rb") as fmd5:
                        md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()
                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <md5 calcolato> " + md5filename)
                        fmd5.close()
                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <è un file...> " + str(file.path)+" LO CHIUDO")
                    srcfile = os.fsdecode(file)
                    dstroot = self.globpropsHash['masterrepository']
                    dstcamerafolder = "ProduttoreNonNoto\\ModelloNonNoto"
                    dstmaker = 'ProduttoreNonNoto'
                    dstmodel = 'ModelloNonNoto'
                    dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                    dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                    dstext = os.path.splitext(file)[1].lower()
                    try:
                        with Image.open(pathlib.Path(file)) as image:
                            info = image.getexif()
                            if info:
                                logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <ha EXIF TAGS>")
                                for (tag, value) in info.items():
                                    decoded = TAGS.get(tag, tag)
                                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <EXIF_TAG:> " + str(tag) + " DECODED_TAG " + str(
                                        TAGS.get(tag, tag)) + " TAG_VALUE: " + str(info[tag]))
                                    if decoded == 'DateTime':
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <Anno/Mese da DataFile:> " + dstyearfolder + "/" + dstmonthfolder)
                                        dstyearfolder = time.strftime("%Y",time.strptime(value,"%Y:%m:%d %H:%M:%S"))
                                        dstmonthfolder = time.strftime("%m", time.strptime(value,"%Y:%m:%d %H:%M:%S"))
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <Anno/Mese da ExifFile:> " + dstyearfolder + "/" + dstmonthfolder)
                                    if decoded == 'Make' and value != '':
                                        dstmaker = value.strip().replace(' ', '')
                                        dstcamerafolder = dstmaker
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <PRODUTTORE:> " + dstmaker)
                                    if decoded == 'Model' and value != '':
                                        dstmodel = value.strip().replace(' ', '-')
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <MODELLO:> " + dstmodel)
                                dstcamerafolder = dstmaker + "\\" + dstmodel
                                logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <FOTOCAMERA:> " + dstcamerafolder)
                    except UnidentifiedImageError:
                        logger.error("Immagine Non identificata")
                    dstfolder = dstroot + "\\" + dstcamerafolder + "\\" + dstyearfolder + "\\" + dstmonthfolder
                    dstfile = dstfolder + "\\" + md5filename + dstext
                    logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <Destinazione individuata:> " + dstfile)
                    self.globpropsHash['masterrepository_bin'] = self.globpropsHash[
                                                                     'masterrepository'] + "\\cestino"
                    self.copymode = self.modoCopia.GetSelection()
                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <CopyMode:> " + str(self.copymode))
                    if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                        os.makedirs(self.globpropsHash['masterrepository_bin'])
                        logger.debug("FOLDER_CESTINO_ARCHIVIO:" + self.globpropsHash['masterrepository_bin'])
                    if not os.path.exists(dstfolder):
                        os.makedirs(dstfolder)
                    if not os.path.exists(dstfile):
                        logger.debug("File: " + dstfile + " Non Esiste, lo copio")
                        try:
                            shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                            logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <<COPIATO File:> " + srcfile + " su " + dstfile)
                            logger.info(
                                "FILE " + str(id_log_counter_dir) + "_" + str(id_log_counter_file) + " <FINE> " + str(
                                    file.path))
                            self.globpropsHash['f_copia']['copied'].append(file.path)
                            if self.copymode == 1:
                                try:
                                    shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                                copy_function='copy2')
                                except IOError as e:
                                    logger.error("<<ERRORE SPOSTAMENTO FILE:>>File: " + srcfile + " su " + dstfile)
                            if self.copymode == 2:
                                try:
                                    send2trash(srcfile)
                                except IOError as e:
                                    logger.error("<<ERRORE CESTINO:>>File: " + srcfile + "****" + str(e))

                        except IOError as e:
                            logger.error("<<ERRORE COPIA>>File: " + srcfile + " su " + dstfile)
                    else:
                        if self.copymode == 1:
                            try:
                                shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                            copy_function='copy2')
                            except IOError as e:
                                logger.error("<<ERRORE SPOSTAMENTO FILE:>>File: " + srcfile + " su " + dstfile)
                        if self.copymode == 2:
                            try:
                                send2trash(srcfile)
                            except IOError as e:
                                logger.error("<<ERRORE CESTINO:>>File: " + srcfile + "****" + str(e))
                        logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter_file)+" <<SKIPPED File:>" + srcfile + " identico a " + md5filename + dstext)
                        logger.info(
                            "FILE " + str(id_log_counter_dir) + "_" + str(id_log_counter_file) + " <FINE> " + str(file.path))
                        self.globpropsHash['f_copia']['skipped'].append(file.path)
            logger.info("<<<"+str(dir)+">>> "+str(id_log_counter_dir)+" <<<FINE CARTELLA>>>")
        else:
            self.importDirError = 1
            dlg = wx.MessageDialog(self, "Directory Import Inesistente", style=wx.ICON_ERROR,
                                   caption="Directory Import Inesistente")
            dlg.ShowModal()


if __name__ == '__main__':
    
    logger = logging.getLogger('photoark')
    stdout = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    stdout.setFormatter(fmt)
    logger.addHandler(stdout)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False    
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoManager")
    PhotoManagerApp.MainLoop()