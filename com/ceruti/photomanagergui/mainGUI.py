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
# NB per cambiare tra pc aziendale e di casa basta commentre/scommentare dove va in errore
# NB pip install --proxy http://user:password@proxy.dominio.it:porta wxPython



# TODO PRINCIPALE: lista task minimali per costruire il nuovo archivio
# 1. alberatura archivio corretta --> fatto  ma correggere conteggio
# 2. impostazione/fix data per foto "sbagliate" --> da fare correggere conteggio
# 3. check duplicati (almeno lista in log e conteggio a video)  --> da finire correggere conteggio
# TODO FORMATTAZIONE LOG
# TODO conteggio file e cartelle in check duplicati archivio
# TODO conteggio errori copia
# TODO conteggio Immagini non identificate e lista dei file non identificati da (eventualemente) pulire
# TODO LOG SU FILE
# TODO CONTROLLO PERMESSI
# TODO sistemare pulsanti e barre di avanzamento
# TODO riorganizzare interfaccia grafica
# TODO EXIF SET GPS DATA ORA
# TODO LIBRERIA PYTHON MD5 al posto dell'esecuzione del comando esterno
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
            match = re.search('^importfolder=(.*)', line)
            if match:
                myHashGlob['importfolder'] = match[1]
                logger.debug("<<Parametro letto nel file #importfolder# " + str(match[1]))
            match = re.search('^importfilelist=(.*)', line)
            if match:
                myHashGlob['importfilelist'] = match[1]
                logger.debug("<<Parametro letto nel file #importfilelist# " + str(match[1]) + "\n")
    return myHashGlob


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title, *args, **kw):
        super().__init__(*args, **kw)
        wx.Panel.__init__(self, parent, title=title, size=(725, 600))
        max_gauge_size = 675
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
        # self.globpropsHash = CheckAndLoadProperties("C:\\Users\\Davide\\PhotoManager", "default.props",".masterrepository.conf")
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n" + str(self.globpropsHash))
        self.importDirFileExtensions = {}
        self.importMd5fileHash = {}
        self.duplicatedFilesDict = {}
        self.duplicatedFilesListValues=[]
        self.skippedfileHash = {}
        self.loggingDict = {}
        self.importDirError = 0
        self.copymode = 0

        self.gauge = wx.Gauge(self, pos=(5, 540), size=(max_gauge_size, -1))
        self.gauge.SetRange(max_gauge_size)
        self.gauge.SetValue(0)
        self.treeTitle = wx.StaticText(self, label="Scegliere Cartella File Da Importare:", pos=(5, 5), size=(345, 25))

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


        self.esci = wx.Button(self, label="ESCI", pos=(5, 400), size=(350, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)

        self.importDirList = wx.GenericDirCtrl(self, pos=(5, 30), size=(345, 230), style=wx.DIRCTRL_DIR_ONLY)
        if 'importfolder' not in self.globpropsHash.keys():
            self.importDirList.SetPath("c:\\temp")
            self.importDirList.SelectPath("c:\\temp", select=True)
        else:
            self.importDirList.SetPath(self.globpropsHash['importfolder'])
            self.importDirList.SelectPath(self.globpropsHash['importfolder'], select=True)
        self.importDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaImportFolder)


        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0, 'tot_dirs':0, 'duplicated_files':0}
        self.SelezionaImportFolder()
        self.SetFocus()
        self.Center()
        self.Show(True)

    def stringFormattedHash(self):
        result = ""
        for k in self.globpropsHash.keys():
            result = result + k + " = " + str(self.globpropsHash[k]) + "\n"
        return result

    def SelezionaImportFolder(self):        
        if self.importDirList.GetPath():
            self.globpropsHash['importfolder'] = self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())

    def AvviaCaricaEstensioni(self, evt):
        logger.debug("**********  %s ",self.globpropsHash['importfolder'])
        messaggioEstensioni = str(loadFileExtensionList(self, self.importDirList.GetPath(), True))
        messaggioFolderImport = self.importDirList.GetPath()
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension = wx.MessageBox(
            "Nel folder import " + messaggioFolderImport + "\nci sono i seguenti tipi di file: \n" + messaggioEstensioni,
            '', wx.CLOSE)
        logger.info(messaggioEstensioni)
        self.gauge.SetValue(0)

    def Esci(self, evt):
        self.Close()
        pass

    def AvviaCopiaFile(self, evt):
        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0}
        self.importDirError = 0
        self.CopiaFile(self.globpropsHash['importfolder'])
        self.duplicatedFilesDict.clear()

        self.skippedfileHash.clear()
        self.gauge.SetValue(self.gauge.GetRange())
        if self.importDirError == 0:
            okMD5 = wx.MessageDialog(self, "Import File Terminato\n\n" + "File copiati: " + str(
                self.fileCounter['copied_files']) + "\nFile saltati: " + str(
                self.fileCounter['skipped_files']) + "\nFile totali: " + str(self.fileCounter['tot_files']),
                                     style=wx.ICON_INFORMATION, caption="Copia Terminata")
            okMD5.ShowModal()
        self.gauge.SetValue(0)

    def AvviaFixDateTime(self, evt):        
        self.Errors = 0
        self.FixDateTime(self.importDirList.GetPath(),0)                
        self.gauge.SetValue(self.gauge.GetRange())
        if self.Errors == 0:
            okCheck = wx.MessageDialog(self, "FUNZIONE DA IMPLEMENTARE - File elaborat\n\nFile analizzati: "+str(self.fileCounter['tot_files'])+"\nSotto cartelle analizzate: "+str(self.fileCounter['tot_dirs']), style=wx.ICON_INFORMATION, caption="Check Terminato")
            okCheck.ShowModal()
        self.gauge.SetValue(0)

    def FixDateTime(self, dir="C:\\Users\\c333053\\TestImport", round=0, dirrecursion=False):
        id_log_counter_dir = str(self.fileCounter['tot_dirs'])
        n = round + self.gauge.GetRange()
        self.fixmode=self.modoFixData.GetSelection()
        if os.path.exists(dir):
            logger.info("<<< %s >>> %s <<<INIZIO CARTELLA>>>",dir,id_log_counter_dir)
            for file in os.scandir(dir):
                id_log_counter = str(self.fileCounter['tot_files'])
                if file.is_dir():                    
                    if self.fixmode==1:
                        logger.debug("DIRECTORY %s_%s <NON ATTRAVERSO LA DIRECTORY> %s",id_log_counter_dir,id_log_counter,str(file.path))                                        
                    else:
                        logger.debug("DIRECTORY %s_%s <ATTRAVERSO LA DIRECTORY> %s",id_log_counter_dir,id_log_counter,str(file.path))  
                        self.FixDateTime(file,n,True)                                      
                else:
                    logger.info("FILE %s_%s <INIZIO> %s",id_log_counter_dir,id_log_counter, file.path)
                    with exiftool.ExifTool() as et:
                        et.execute(file.path)
                        #print("TESTONE_OUT "+str(et.last_stdout))
                        #print("TESTONE_ERROR "+str(et.last_stderr))
                        logger.debug("FILE %s_%s <STDOUT CMD EXIFTOOL %s > ",id_log_counter_dir,id_log_counter,str(et.last_stdout))
                        logger.debug("FILE %s_%s <STDERR CMD EXIFTOOL %s > ",id_log_counter_dir,id_log_counter,str(et.last_stderr))
                        logger.debug("FILE %s_%s <RISULTATO CMD EXIFTOOL %s",id_log_counter_dir,id_log_counter,str(et.last_status))
                n+=1
            logger.info("<<< %s >>> %s <<<FINE CARTELLA>>>",str(dir),id_log_counter_dir)

    





    def AvviaCheckArchivio(self, evt):
        
        #self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0 ,'tot_dirs': 0}
        self.duplicatedFilesDict.clear()
        self.Errors = 0
        self.CheckArchivio(self.globpropsHash['importfolder'])                
        self.gauge.SetValue(self.gauge.GetRange())
        logger.info("Dictionary File Trovati: ")
        for k in self.duplicatedFilesDict.keys():
            logger.info("chiave >>> %s  valore >>> %s",k,self.duplicatedFilesDict[k])
        if self.Errors == 0:
            okCheck = wx.MessageDialog(self, "FUNZIONE DA IMPLEMENTARE - Check Archivio Terminato\n\nFile analizzati: "+str(self.fileCounter['tot_files'])+"\nSotto cartelle analizzate: "+str(self.fileCounter['tot_dirs']), style=wx.ICON_INFORMATION, caption="Check Terminato")
            okCheck.ShowModal()
            


        self.gauge.SetValue(0)

    def CheckArchivio(self, dir="C:\\Users\\c333053\\TestImport", round=0):
        id_log_counter_dir = str(self.fileCounter['tot_dirs'])
        n = round + self.gauge.GetRange()
        if os.path.exists(dir):
            logger.info("<<< %s >>> %s <<<INIZIO CARTELLA>>>",dir,id_log_counter_dir)
            for file in os.scandir(dir):
                id_log_counter = str(self.fileCounter['tot_files'])
                if file.is_dir():                    
                    logger.debug("FILE %s_%s <è una directory> %s",id_log_counter_dir,id_log_counter,str(file.path))                    
                    self.CheckArchivio(file, n)
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
                n+=1
            logger.info("<<< %s >>> %s <<<FINE CARTELLA>>>",str(dir),id_log_counter_dir)

    def CopiaFile(self, dir="C:\\Users\\c333053\\TestImport", round=0):
        id_log_counter_dir = self.fileCounter['tot_files']
        n = round + self.gauge.GetRange()
        if os.path.exists(dir):
            logger.info("<<<"+str(dir)+">>> "+str(id_log_counter_dir)+" <<<INIZIO CARTELLA>>>")
            for file in os.scandir(dir):
                id_log_counter = self.fileCounter['tot_files']
                if file.is_dir():
                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <è una directory> " + str(file.path))
                    self.CopiaFile(file, n)
                else:
                    logger.info("FILE " + str(id_log_counter_dir)+"_"+str(id_log_counter) + " <INIZIO> " + str(file.path))
                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <è un file...> " + str(file.path)+" LO APRO")
                    with open(file, "rb") as fmd5:
                        md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()
                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <md5 calcolato> " + md5filename)
                        fmd5.close()
                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <è un file...> " + str(file.path)+" LO CHIUDO")
                    srcfile = os.fsdecode(file)
                    dstroot = self.globpropsHash['masterrepository']
                    dstcamerafolder = "ProduttoreNonNoto\\ModelloNonNoto"
                    dstmaker = 'ProduttoreNonNoto'
                    dstmodel = 'ModelloNonNoto'
                    dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                    dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                    dstext = os.path.splitext(file)[1].lower()
                    self.fileCounter['tot_files'] = self.fileCounter['tot_files'] + 1
                    try:
                        with Image.open(pathlib.Path(file)) as image:
                            info = image.getexif()
                            if info:
                                logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <ha EXIF TAGS>")
                                for (tag, value) in info.items():
                                    decoded = TAGS.get(tag, tag)
                                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <EXIF_TAG:> " + str(tag) + " DECODED_TAG " + str(
                                        TAGS.get(tag, tag)) + " TAG_VALUE: " + str(info[tag]))
                                    if decoded == 'DateTime':
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <Anno/Mese da DataFile:> " + dstyearfolder + "/" + dstmonthfolder)
                                        dstyearfolder = time.strftime("%Y",time.strptime(value,"%Y:%m:%d %H:%M:%S"))
                                        dstmonthfolder = time.strftime("%m", time.strptime(value,"%Y:%m:%d %H:%M:%S"))
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <Anno/Mese da ExifFile:> " + dstyearfolder + "/" + dstmonthfolder)
                                    if decoded == 'Make' and value != '':
                                        dstmaker = value.strip().replace(' ', '')
                                        dstcamerafolder = dstmaker
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <PRODUTTORE:> " + dstmaker)
                                    if decoded == 'Model' and value != '':
                                        dstmodel = value.strip().replace(' ', '-')
                                        logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <MODELLO:> " + dstmodel)
                                dstcamerafolder = dstmaker + "\\" + dstmodel
                                logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <FOTOCAMERA:> " + dstcamerafolder)

                    except UnidentifiedImageError:
                        logger.error("Immagine Non identificata")
                    dstfolder = dstroot + "\\" + dstcamerafolder + "\\" + dstyearfolder + "\\" + dstmonthfolder
                    dstfile = dstfolder + "\\" + md5filename + dstext
                    logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <Destinazione individuata:> " + dstfile)
                    self.globpropsHash['masterrepository_bin'] = self.globpropsHash[
                                                                     'masterrepository'] + "\\cestino"
                    self.copymode = self.modoCopia.GetSelection()
                    logger.debug("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <CopyMode:> " + str(self.copymode))
                    if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                        os.makedirs(self.globpropsHash['masterrepository_bin'])
                        logger.debug("FOLDER_CESTINO_ARCHIVIO:" + self.globpropsHash['masterrepository_bin'])
                    if not os.path.exists(dstfolder):
                        os.makedirs(dstfolder)
                    if not os.path.exists(dstfile):
                        logger.debug("File: " + dstfile + " Non Esiste, lo copio")
                        try:
                            shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                            logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <<COPIATO File:> " + srcfile + " su " + dstfile)
                            logger.info(
                                "FILE " + str(id_log_counter_dir) + "_" + str(id_log_counter) + " <FINE> " + str(
                                    file.path))
                            self.fileCounter['copied_files'] = self.fileCounter['copied_files'] + 1
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
                        logger.info("FILE "+str(id_log_counter_dir)+"_"+str(id_log_counter)+" <<SKIPPED File:>" + srcfile + " identico a " + md5filename + dstext)
                        logger.info(
                            "FILE " + str(id_log_counter_dir) + "_" + str(id_log_counter) + " <FINE> " + str(file.path))
                        self.fileCounter['skipped_files'] = self.fileCounter['skipped_files'] + 1
                n += 1
                if n >= self.gauge.GetRange():
                    self.gauge.Pulse()
                else:
                    self.gauge.SetValue(n)
            logger.info("<<<"+str(dir)+">>> "+str(id_log_counter_dir)+" <<<FINE CARTELLA>>>")
        else:
            self.importDirError = 1
            dlg = wx.MessageDialog(self, "Directory Import Inesistente", style=wx.ICON_ERROR,
                                   caption="Directory Import Inesistente")
            dlg.ShowModal()


if __name__ == '__main__':
    
    logger = logging.getLogger('photoark')
    
    #logger.propagate = False
    #logger.setLevel(logging.DEBUG)
    #ch = logging.StreamHandler()
    #formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(msg)s')
    #ch.setFormatter(formatter)
    #logger.addHandler(ch)

    
    
    #logger = logging.getLogger('photoark')
    
    stdout = logging.StreamHandler()
    
    #fmt = logging.Formatter("%(name)s: %(asctime)s | %(levelname)s | %(filename)s%(lineno)s | %(process)d >>> %(message)s")
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    stdout.setFormatter(fmt)
    logger.addHandler(stdout)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    





    
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoManager")
    PhotoManagerApp.MainLoop()