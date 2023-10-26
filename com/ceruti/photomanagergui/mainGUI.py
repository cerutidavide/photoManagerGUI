import datetime
import hashlib
import logging
import os
import pathlib
import re
import shutil
import time
from datetime import datetime

import exiftool
import wx
import wx.dataview
from PIL import Image
from PIL import UnidentifiedImageError
from PIL.ExifTags import TAGS
from PIL.TiffTags import TAGS
from send2trash import send2trash


# NB per cambiare tra pc aziendale e di casa basta commentre/scommentare dove va in errore
# NB pip install --proxy http://user:password@proxy.dominio.it:porta wxPython
# >>> stringa='2023_10_20_10_56_34.368481_2023_10_20_10_53_56.900199_2023_10_20_10_52_44.222646_2023_10_19_16_43_01.178484_0a6157af3a585ba3add55c451ff2123c(1).jpg'          
# >>> match=re.search('.*_(.*)\.',stringa)
# >>> print(match[1])
# 0a6157af3a585ba3add55c451ff2123c(1)
# >>> match=re.search('.*_(.*)\.(.*)',stringa) 
# >>> print(match[1])
# 0a6157af3a585ba3add55c451ff2123c(1)
# >>> print(match[2]) 
# jpg

# TODO PRINCIPALE: lista task minimali per costruire il nuovo archivio
#   1. Restore della cartella backup da un'altra parte (Work-area?)
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


def LoadPropertiesAndInitArchive(basePath='c:\\Utenti\\Davide\\photoManagerGUI',
                           filenameGlob="default.props", filenameMstr=".masterrepository.conf"):
    myHashGlob = {}
    myHashGlob['fileconfprincipale'] = filenameGlob
    logger.debug("<<Parametro impostato #file_di_configurazione_principale# " + os.path.join(basePath, filenameGlob))
    myHashGlob['masterrepositoryconf'] = filenameMstr
    logger.debug("<<Parametro impostato #masterrepositoryconf# " + filenameMstr)
    with open(os.path.join(basePath, filenameGlob), encoding="utf-8") as f:
        for line in f.readlines():
            # print(line)
            match = re.search('^masterrepository=(.*)', line)
            # print(match)
            if match:
                myHashGlob['masterrepository'] = match[1]
                logger.debug("<<Parametro letto nel file #masterrepository# " + str(match[1]))
            match = re.search('^selectedfolder=(.*)', line)
            if match:
                myHashGlob['selectedfolder'] = match[1]
                logger.debug("<<Parametro letto nel file #selectedfolder# " + str(match[1]))                        
            myHashGlob['masterrepository_bin'] = myHashGlob['masterrepository']+"\\recycled-bin"
            myHashGlob['masterrepository_bak'] = myHashGlob['masterrepository']+"\\backup"
            myHashGlob['masterrepository_bak'] = myHashGlob['masterrepository']+"\\work-area"
            myHashGlob['f_copia'] = dict()
            myHashGlob['f_copia']['copied'] = []
            myHashGlob['f_copia']['skipped'] = []
            myHashGlob['f_copia']['tot_files'] = []
            myHashGlob['f_copia']['tot_dirs'] = []
            
            myHashGlob['f_listaestensioni'] = dict()
            
            myHashGlob['f_checkarchivio'] = dict()

            myHashGlob['f_fixdate'] = dict()
            myHashGlob['f_fixdate']['fixed'] = []
            myHashGlob['f_fixdate']['skipped'] = []
            myHashGlob['f_fixdate']['tot_files'] = []
            myHashGlob['f_fixdate']['tot_dirs'] = []

            myHashGlob['f_checkmd5backup'] = dict()
            myHashGlob['f_checkmd5backup']['matched'] = []
            myHashGlob['f_checkmd5backup']['nomatch'] = []
            myHashGlob['f_checkmd5backup']['tot_files'] = []
            myHashGlob['f_checkmd5backup']['tot_dirs'] = []
            myHashGlob['f_checkmd5backup']['error_files']=[]

            myHashGlob['f_restore'] = dict()
            myHashGlob['f_restore']['restored'] = []
            myHashGlob['f_restore']['skipped'] = []
            myHashGlob['f_restore']['tot_files'] = []
            myHashGlob['f_restore']['tot_dirs'] = []
            myHashGlob['f_restore']['reading_error_files'] = []

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
        logger.info("###basePath PER AZIENDALE: C:\\Users\\Davide\\PhotoManager ###")
        logger.info("###basePath PER PC CASA:   C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master ###\n")
        
        self.globpropsHash = LoadPropertiesAndInitArchive(self.basePath, self.baseFile, ".masterrepository.conf")
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))

        


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
        if 'selectedfolder' not in self.globpropsHash.keys():
            self.workingDirList.SetPath("c:\\temp")
            self.workingDirList.SelectPath("c:\\temp", select=True)
            self.globpropsHash['selectedfolder']="C:\\temp"
        else:
            self.workingDirList.SetPath(self.globpropsHash['selectedfolder'])
            self.workingDirList.SelectPath(self.globpropsHash['selectedfolder'], select=True)
        self.workingDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaWorkingDir)



        self.treeTitle = wx.StaticText(self, label="Scegliere Cartella di lavoro per le azioni sulla destra:", pos=(5, 5), size=(345, 25))

        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),
                                          pos=(360, 400))

        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file Cartella Selezionata",
                                                    pos=(360, 30),size=(345,-1))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)
        self.avviaCopiaFile = wx.Button(self, label="Avvia Import In Archivio Master", pos=(360, 90),size=(345,-1))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.modoCopia = wx.RadioBox(self, label="Azione Su File IMPORTATI/SKIPPATI:", majorDimension=3,
                                     pos=(360, 120), size=(345, -1),
                                     choices=["nessuna azione", "cestino archivio", "cestino windows"])
        self.avviaCheckArchivio = wx.Button(self, label="Avvia Controllo Duplicati Cartella Selezionata", pos=(360, 55),size=(345,-1))
        self.avviaCheckArchivio.Bind(wx.EVT_BUTTON, self.AvviaCheckArchivio)

        self.avviaFixDateTime = wx.Button(self, label="Avvia Fix Orario Cartella Selezionata", pos=(360, 180),size=(345,-1))
        self.avviaFixDateTime.Bind(wx.EVT_BUTTON, self.AvviaFixDateTime)
        self.modoFixData = wx.RadioBox(self, label="Attraversare Sotto Cartelle Sì/No", majorDimension=2,
                                     pos=(360, 210), size=(345, -1),
                                     choices=["Sì", "No"])
        self.avviaCheckMd5Backup = wx.Button(self, label="Avvia Check Md5 per folder selezionato", pos=(360, 280),size=(345,-1))
        self.avviaCheckMd5Backup.Bind(wx.EVT_BUTTON, self.AvviaCheckMd5Backup)


        self.esci = wx.Button(self, label="ESCI", pos=(360, 350), size=(345, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)

        self.outputWindow = wx.TextCtrl(self, pos=(5, 280), size=(345, 300),style=wx.TE_MULTILINE)
        

        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0, 'tot_dirs':0, 'duplicated_files':0}
        
        self.SetFocus()
        self.Center()
        self.Show(True)
   
    def CleanConfigFunction(self):
        for k in self.globpropsHash.keys():
            logger.info('CHIAVE: %s',str(k))
            if str(k).startswith('f_'):
                for c in self.globpropsHash[k].keys():
                    logger.debug('DICT DA SVUOTARE [%s][%s]',str(k),str(c))
                    logger.debug('VALORE DICT DA SVUOTARE %s',str(self.globpropsHash[k][c]))
                    self.globpropsHash[k][c].clear()
            


        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())
    def stringFormattedHash(self):
        result = ""
        for k in self.globpropsHash.keys():
            result = result + k + " = " + str(self.globpropsHash[k]) + "\n"
        return result
    def SelezionaWorkingDir(self,evt):        
        if self.workingDirList.GetPath():
            self.globpropsHash['selectedfolder'] = self.workingDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())
    def AvviaCaricaEstensioni(self, evt):
        logger.debug("**********  %s ",self.globpropsHash['selectedfolder'])
        messaggioEstensioni = str(loadFileExtensionList(self, self.globpropsHash['selectedfolder'], True))
        messaggioFolderImport =self.globpropsHash['selectedfolder']
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension = wx.MessageBox(
            "Nel folder import " + messaggioFolderImport + "\nci sono i seguenti tipi di file: \n" + messaggioEstensioni,
            '', wx.CLOSE)
        logger.info(messaggioEstensioni)
        self.gauge.SetValue(0)

    def Esci(self, evt):
        self.Close()
        pass

    def CheckMd5Backup(self, dir="C:\\Users\\c333053\\TestImport", dirrecursion=False):
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_checkmd5backup']['tot_dirs']))
            logger.info("<<<INIZIO CARTELLA %s >>>",dir)
            self.globpropsHash['f_checkmd5backup']['tot_dirs'].append(dir)
            dir_iterator=os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    logger.debug("DIRECTORY %s <ATTRAVERSO LA DIRECTORY> %s",id_log_counter_dir,str(file.path))
                    self.CheckMd5Backup(file,True)
                else:
                    id_log_counter = str(len(self.globpropsHash['f_checkmd5backup']['tot_files']))
                    logger.info("FILE %s_%s %s <Inizio",id_log_counter_dir,id_log_counter,file.path)
                    self.globpropsHash['f_checkmd5backup']['tot_files'].append(file.path)
                    try: 
                        fmd5=open(file, "rb")
                        logger.debug("FILE %s_%s %s <Aperto>",id_log_counter_dir,id_log_counter,file.path)
                        
                        


                        match=re.search('.*_(.*)\.',str(file.name))
                        if match:
                            logger.debug("FILE %s_%s <md5 ricavato nome file> %s",id_log_counter_dir,id_log_counter,match[1])
                            read_md5filename=match[1]
                            calculated_md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()+pathlib.Path(file).suffix.replace('_original','')

                        else:
                            logger.debug("FILE %s_%s <Il file  %s non presenta la struttura di un file di backup ",id_log_counter_dir,id_log_counter,file.name)
                            calculated_md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()+pathlib.Path(file).suffix
                            read_md5filename=file.name


                        #ah cazzo estensione non va bene (gli va tolto original ovunque)


                        logger.debug("FILE %s %s  <file name con md5 calcolato> %s <file name preso dal nomefile> %s ",str(id_log_counter_dir),str(id_log_counter),calculated_md5filename,read_md5filename)
                        if (calculated_md5filename==read_md5filename):
                            logger.debug("FILE %s %s  <MD5 MATCH per il file %s ",str(id_log_counter_dir),str(id_log_counter),file.name)
                            logger.info("FILE %s %s  <FILE ORIGINALE DA RESTORARE %s ",str(id_log_counter_dir),str(id_log_counter),file.name) 
                            
                            
                            
                            
                            
                            #self.globpropsHash['f_checkmd5backup']['original-restored'].append(file.path)
                        else:
                            logger.debug("FILE %s %s  <MD5 NO MATCH per il file %s ",str(id_log_counter_dir),str(id_log_counter),file.name)                                                        
                            logger.info("FILE %s %s  <FILE CON METADATI MODIFICATI RISPETTO AL FILE ORIGINALE DA RESTORARE %s ",str(id_log_counter_dir),str(id_log_counter),file.path) 
                            #self.globpropsHash['f_checkmd5backup']['non-original-restored'].append(file.path)

                        #NON FUNZIONA!!!!! devi far sparire _original e timestamps se no non funziona mai

                        #QUI
                        # >>> stringa='2023_10_20_10_56_34.368481_2023_10_20_10_53_56.900199_2023_10_20_10_52_44.222646_2023_10_19_16_43_01.178484_0a6157af3a585ba3add55c451ff2123c(1).jpg'          
# >>> match=re.search('.*_(.*)\.',stringa)
# >>> print(match[1])
# 0a6157af3a585ba3add55c451ff2123c(1)
# >>> match=re.search('.*_(.*)\.(.*)',stringa) 
# >>> print(match[1])
# 0a6157af3a585ba3add55c451ff2123c(1)
# >>> print(match[2]) 

                     
                     
                     
                        # logger.debug("FILE %s_%s <file da cui estrarre md5> %s",id_log_counter_dir,id_log_counter,file.name)
                        fmd5.close()
                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <è un file...> " + str(file.path)+" LO CHIUDO")
                    except FileNotFoundError as e:
                        logger.error("<<ERRORE APERTURA FILE: %s ",file.path)                                                    
                        self.globpropsHash['f_checkmd5backup']['reading_error_files'].append(file.path)
            dir_iterator.close()
            logger.info("<<<FINE CARTELLA>>> <<< %s >>>",dir)
    def AvviaCheckMd5Backup(self,evt):
        self.CleanConfigFunction()
        self.CheckMd5Backup(self.globpropsHash['selectedfolder'],False)
        self.gauge.SetValue(self.gauge.GetRange())
        logger.info("Dictionary File Da trattare: ")
        outputWindowText=''
        outputWindowText+='<<<< FILE Match MD5: '+str(len(self.globpropsHash['f_checkmd5backup']['matched']))+' >>>>\n'
        n=1
        for f in self.globpropsHash['f_checkmd5backup']['matched']:
            logger.info("matched file >>> %s ",f)
            outputWindowText+=str(n)+'-->'+f+"\n"
            n+=1
        outputWindowText+='\n<<<< FILE NO MATCH: '+str(len(self.globpropsHash['f_checkmd5backup']['nomatch']))+' >>>>\n'
        n=1
        for s in self.globpropsHash['f_checkmd5backup']['nomatch']:
            logger.info("no-matched file >>> %s ",s)
            outputWindowText+=str(n)+'-->'+s+"\n"
            n+=1
        logger.debug("Numero di file Match: %s",len(self.globpropsHash['f_checkmd5backup']['matched']))
        logger.debug("Numero di file NO-Match: %s",len(self.globpropsHash['f_checkmd5backup']['nomatch']))
        self.outputWindow.SetValue(outputWindowText)
        self.gauge.SetValue(0)
        self.CleanConfigFunction()



    def AvviaRestore(self,evt):
        self.CleanConfigFunction()


    def AvviaFixDateTime(self, evt):        
        self.CleanConfigFunction()
        self.FixDateTime(self.globpropsHash['selectedfolder'],False)
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
        okCheck = wx.MessageDialog(self, "File aggiornati: "+str(len(self.globpropsHash['f_fixdate']['fixed']))+" su un totale di "+str(len(self.globpropsHash['f_fixdate']['tot_files']))+"\nFile saltati: "+str(len(self.globpropsHash['f_fixdate']['skipped']))+"\nCartelle percorse: "+str(len(self.globpropsHash['f_fixdate']['tot_dirs'])), style=wx.ICON_INFORMATION, caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()
    def FixDateTime(self, dir="C:\\Users\\c333053\\TestImport", dirrecursion=False):        
        #check self.AvviaCheckArchivio(self,wx.EVT_BUTTON)
        self.fixmode=self.modoFixData.GetSelection()
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_fixdate']['tot_dirs']))
            logger.info("<<<INIZIO CARTELLA %s >>>",dir)
            self.globpropsHash['f_fixdate']['tot_dirs'].append(dir)
            dir_iterator=os.scandir(dir)
            for file in dir_iterator:
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
                        #Al momento fisso a -7 ore
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
            dir_iterator.close()
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
        self.CheckArchivio(self.globpropsHash['selectedfolder'])                
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
            dir_iterator=os.scandir(dir)
            for file in dir_iterator:
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
            dir_iterator.close()
            logger.info("<<< %s >>> %s <<<FINE CARTELLA>>>",str(dir),id_log_counter_dir)
    def AvviaCopiaFile(self, evt):
        self.CleanConfigFunction()
        logger.debug("###PARAMETRI DI CONFIGURAZIONE PRIMA DELL INIZIO COPIA###  \n" + str(self.globpropsHash))
        self.importDirError = 0
        self.CopiaFile(self.globpropsHash['selectedfolder'])
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
            dir_iterator=os.scandir(dir)
            for file in dir_iterator:
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
            dir_iterator.close()
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