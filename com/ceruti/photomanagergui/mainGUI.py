import logging
import os
import re
import shutil
import subprocess
import time
import wx
import io, hashlib, hmac
from send2trash import send2trash
from PIL import Image
import pathlib
from PIL import ExifTags
from PIL.ExifTags import TAGS
from PIL import UnidentifiedImageError
from PIL.TiffTags import TAGS
from PIL.TiffTags import TYPES
from PIL import TiffTags
from PIL import Image
from PIL.TiffTags import TAGS

# NB per cambiare tra pc aziendale e di casa basta commentre/scommentare dove va in errore    righe 97 e 98
# NB pip install --proxy http://user:password@proxy.dominio.it:porta wxPython


# TODO FORMATTAZIONE LOG
# TODO conteggio errori copia
# TODO conteggio Immagini non identificate e lista dei file non identificati da (eventualemente) pulire
# TODO modificare alberatura per gestire modello MACCHINA FOTOGRAFICA
# TODO LOG SU FILE
# TODO CONTROLLO PERMESSI
# TODO sistemare pulsanti e barre di avanzamento
# TODO riorganizzare interfaccia grafica
# TODO EXIF SISTEMAZIONE DATA ORA
# TODO EXIF SET GPS DATA ORA
# TODO LIBRERIA PYTHON MD5 al posto dell'esecuzione del comando esterno
# modello fotocamera default=FotocameraNonNota se in exif c'è, sovrascrivo
#
#



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
    logger.debug("<<Parametro impostato #file_di_configurazione_principale# "+os.path.join(workingdir, filenameGlob))
    myHashGlob['masterrepositoryconf'] = filenameMstr
    logger.debug("<<Parametro impostato #masterrepositoryconf# "+filenameMstr)
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
                logger.debug("<<Parametro letto nel file #importfilelist# " + str(match[1])+"\n")
    return myHashGlob


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title):
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        max_gauge_size = 675
        self.checkRunning = True
        #self.basePath="C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master"
        self.basePath="C:\\Users\\Davide\\PhotoManager"
        self.baseFile="default.props"
        logger.info("###PARAMETRO FILE BASE### "+self.basePath+"\\"+self.baseFile+"\n")
        logger.info("###MODIFICARE basePath PER AZIENDALE: C:\\Users\\Davide\\PhotoManager ###")
        logger.info("###MODIFICARE basePath PER PC CASA:   C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master ###\n")
        self.globpropsHash=CheckAndLoadProperties(self.basePath,self.baseFile,".masterrepository.conf")
        #self.globpropsHash = CheckAndLoadProperties("C:\\Users\\Davide\\PhotoManager", "default.props",".masterrepository.conf")
        logger.info("###PARAMETRI DI CONFIGURAZIONE###  \n"+str(self.globpropsHash))
        self.importDirFileExtensions = {}
        self.importfileHash = {}
        self.importMd5fileHash = {}
        self.mstrfileHash = {}
        self.copyfileHash = {}
        self.skippedfileHash = {}
        self.loggingDict = {}
        self.importDirError = 0
        self.copymode = 0

        self.gauge = wx.Gauge(self, pos=(5, 540), size=(max_gauge_size, -1))
        self.gauge.SetRange(max_gauge_size)
        self.gauge.SetValue(0)
        self.treeTitle = wx.StaticText(self, label="Scegliere Cartella File Da Importare:", pos=(5, 5), size=(345, 25))

        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),
                                          pos=(355, 5))

        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file presenti nel folder Import ",
                                                    pos=(5, 300))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)
        self.avviaCopiaFile = wx.Button(self, label="Avvia Import In Archivio Master", pos=(5, 325))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.esci = wx.Button(self, label="ESCI", pos=(5, 450), size=(350, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)

        self.importDirList = wx.GenericDirCtrl(self, pos=(5, 30), size=(345, 200), style=wx.DIRCTRL_DIR_ONLY)
        self.importDirList.SetPath("c:\\temp")
        self.importDirList.SelectPath("c:\\temp", select=True)
        self.importDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaImportFolder)

        self.modoCopia = wx.RadioBox(self, label="Azione Su File Importati/Saltati:", majorDimension=3,
                                     pos=(5, 230), size=(345, -1),
                                     choices=["nessuna azione", "cestino archivio", "cestino windows"])

        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0}
        self.SetFocus()
        self.loggerFS = logging.getLogger("filesystemstuff")
        self.Center()
        self.Show(True)

    def stringFormattedHash(self):
        result = ""
        for k in self.globpropsHash.keys():
            result = result + k + " = " + str(self.globpropsHash[k]) + "\n"
        return result

    def SelezionaImportFolder(self, evt):
        if self.importDirList.GetPath():
            self.globpropsHash['importfolder'] = self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())

    def AvviaCaricaEstensioni(self, evt):
        logger.debug("**********   " + self.globpropsHash['importfolder'])
        self.SelezionaImportFolder(evt)
        logger.debug("**********   " + self.globpropsHash['importfolder'])
        messaggioEstensioni = str(loadFileExtensionList(self, self.globpropsHash['importfolder'], True))
        messaggioFolderImport = self.globpropsHash['importfolder']
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension = wx.MessageBox(
            "Nel folder import " + messaggioFolderImport + "\nci sono i seguenti tipi di file: \n" + messaggioEstensioni,
            '', wx.CLOSE)
        logger.info(messaggioEstensioni)

        self.gauge.SetValue(0)

    def TestExif(self, evt):
        for file in os.scandir(self.globpropsHash['importfolder']):
            if file.is_dir():
                logger.info("DIR: " + str(file.path))
            else:
                logger.debug("FILE: " + str(file.path))
                logger.debug('MODIFIED Datetime: ' + time.ctime(os.path.getmtime(file)))
                logger.debug('CREATED Datetime: ' + time.ctime(os.path.getctime(file)))
                with Image.open(pathlib.Path(file)) as image:
                    try:
                        exifData = {}
                        info = image.getexif()
                        if info:
                            for (tag, value) in info.items():
                                decoded = TAGS.get(tag, tag)
                                exifData[decoded] = value
                                logger.debug(image.filename + ' EXIF_TAG: ' + str(decoded) + ' ' + str(value))
                                if decoded == 'DateTime':
                                    logger.info(
                                        'EXIF DateTime: ' + time.asctime(time.strptime(value, "%Y:%m:%d %H:%M:%S")))
                    except BaseException as e:
                        pass
                        logging.error(str(e))

    def Esci(self, evt):
        self.Close()
        pass
    def AvviaCopiaFile(self, evt):
        self.fileCounter = {'tot_files': 0, 'copied_files': 0, 'skipped_files': 0}
        self.importDirError = 0
        self.CopiaFile(self.globpropsHash['importfolder'])
        self.mstrfileHash.clear()
        self.importfileHash.clear()
        self.copyfileHash.clear()
        self.skippedfileHash.clear()
        self.gauge.SetValue(self.gauge.GetRange())
        if self.importDirError == 0:
            okMD5 = wx.MessageDialog(self, "Import File Terminato\n\n" + "File copiati: " + str(
                self.fileCounter['copied_files']) + "\nFile saltati: " + str(
                self.fileCounter['skipped_files']) + "\nFile totali: " + str(self.fileCounter['tot_files']),
                                     style=wx.ICON_INFORMATION, caption="Copia Terminata")
            okMD5.ShowModal()
        self.gauge.SetValue(0)

    def CopiaFile(self, dir="C:\\Users\\c333053\\TestImport", round=0):
        n = round + self.gauge.GetRange()
        if os.path.exists(dir):
            for file in os.scandir(dir):
                logger.debug("\n\nFILE CORRENTE>>>>>" + str(file.path))
                if file.is_dir():
                    logger.debug("CopiaFile.DIR: " + str(file.path))
                    self.CopiaFile(file, n)
                else:
                    logger.debug("CopiaFile.FILE: " + str(file.path))
                    md5command = 'certutil -hashfile \"' + str(file.path) + '\" MD5'
                    logger.debug(md5command)
                    #SEZIONE PROVA CALCOLO MD5 senza esecuzione comando
                    with open(file, "rb") as fmd5:
                        digest = hashlib.file_digest(fmd5, "md5")
                        logger.debug(digest.hexdigest())
                    #SEZIONE PROVA CALCOLO MD5 senza esecuzione comando
                    p = subprocess.run(md5command, shell=True, universal_newlines=True, stdout=subprocess.PIPE)
                    if p.returncode == 0:
                        srcfile = os.fsdecode(file)
                        dstroot = self.globpropsHash['masterrepository']
                        logger.debug("File Sorgente: " + srcfile)
                        dstcamerafolder="ProduttoreNonNoto\\ModelloNonNoto"
                        dstmaker='ProduttoreNonNoto'
                        dstmodel='ModelloNonNoto'
                        dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                        dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                        md5filename = str(p.stdout).split('\n')[1]
                        dstext = os.path.splitext(file)[1].lower()
                        logger.debug("<md5filename> "+md5filename)
                        logger.debug("<ext> "+dstext)
                        logger.debug("FILE: " + str(file.path))
                        self.fileCounter['tot_files'] = self.fileCounter['tot_files'] + 1
                        try:
                            with Image.open(pathlib.Path(file)) as image:
                                info = image.getexif()
                                if info:
                                    logger.debug("info EXIF non è nullo")

                                    for chiave in info.keys() :
                                        logger.debug("CHIAVE: "+str(chiave) + " CHIAVE_DECODED "+ str(TAGS.get(chiave,chiave)) + " VALORE: "+str(info[chiave]))

                                    for (tag, value) in info.items():
                                        decoded = TAGS.get(tag, tag)
                                        logger.debug(
                                            image.filename + ' EXIF_TAG: ' + str(decoded) + ' ' + str(value))
                                        if decoded == 'DateTime':
                                            logger.debug("FILE: " + str(
                                                file.path) + " FILE_Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)
                                            logger.debug('EXIF DateTime: ' + time.asctime(
                                                time.strptime(value, "%Y:%m:%d %H:%M:%S")))
                                            logger.debug('EXIF Presente Anno_PRE:' + dstyearfolder)
                                            logger.debug('EXIF Presente Mese_PRE:' + dstmonthfolder)
                                            dstyearfolder = time.strftime("%Y",
                                                                            time.strptime(value, "%Y:%m:%d %H:%M:%S"))
                                            dstmonthfolder = time.strftime("%m", time.strptime(value,
                                                                                                "%Y:%m:%d %H:%M:%S"))
                                            logger.debug('EXIF Presente Anno_POST:' + dstyearfolder)
                                            logger.debug('EXIF Presente Mese_POST:' + dstmonthfolder)
                                            logger.debug("FILE: " + str(
                                                file.path) + " EXIF_Nuovo Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)
                                        if decoded == 'Make' and value!='':
                                            dstmaker=value.strip().replace(' ','')
                                            dstcamerafolder=dstmaker
                                            logger.debug("PRODUTTORE: "+dstmaker)
                                        if decoded == 'Model' and value!='':
                                            dstmodel=value.strip().replace(' ','-')
                                            logger.debug("MODELLO: "+dstmodel)
                                    dstcamerafolder=dstmaker+"\\"+dstmodel
                                    logger.debug("FOTOCAMERA: "+dstcamerafolder)

                        except UnidentifiedImageError:
                            logging.error("Immagine Non identificata")
                        dstfolder = dstroot + "\\" + dstcamerafolder + "\\" + dstyearfolder + "\\" + dstmonthfolder
                        dstfile = dstfolder + "\\" + md5filename + dstext
                        logger.debug("File Destinazione: " + dstfile)
                        self.globpropsHash['masterrepository_bin'] = self.globpropsHash[
                                                                         'masterrepository'] + "\\cestino"
                        self.copymode = self.modoCopia.GetSelection()
                        logger.debug("SELEZIONE BOTTONE: " + str(self.copymode))
                        if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                            os.makedirs(self.globpropsHash['masterrepository_bin'])
                            logger.debug("FOLDER_CESTINO_ARCHIVIO:" + self.globpropsHash['masterrepository_bin'])
                        if not os.path.exists(dstfolder):
                            os.makedirs(dstfolder)
                        if not os.path.exists(dstfile):
                            logger.debug("File: " + dstfile + " Non Esiste, lo copio")
                            try:
                                shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                                logger.info("<<COPIATO>>File: " + srcfile + " su " + dstfile)
                                self.fileCounter['copied_files'] = self.fileCounter['copied_files'] + 1
                                if self.copymode == 1:
                                    try:
                                        shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                                    copy_function='copy2')
                                    except IOError as e:
                                        logging.error("<<ERRORE SPOSTAMENTO FILE:>>File: " + srcfile + " su " + dstfile)
                                if self.copymode == 2:
                                    try:
                                        send2trash(srcfile)
                                    except IOError as e:
                                        logging.error("<<ERRORE CESTINO:>>File: " + srcfile + "****" + str(e))

                            except IOError as e:
                                logging.error("<<ERRORE COPIA>>File: " + srcfile + " su " + dstfile)
                        else:
                            if self.copymode == 1:
                                try:
                                    shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                                copy_function='copy2')
                                except IOError as e:
                                    logging.error("<<ERRORE SPOSTAMENTO FILE:>>File: " + srcfile + " su " + dstfile)
                            if self.copymode == 2:
                                try:
                                    send2trash(srcfile)
                                except IOError as e:
                                    logging.error("<<ERRORE CESTINO:>>File: " + srcfile + "****" + str(e))
                            logger.info("<<SKIPPED>>File: " + srcfile + " identico a " + md5filename + dstext)
                            self.fileCounter['skipped_files'] = self.fileCounter['skipped_files'] + 1
                    else:
                        logger.debug("Errore nel file: " + str(file.path))
                        errorMD5 = wx.MessageDialog(self, "Calcolo MD5 con errori per il file: " + str(file.path),
                                                    style=wx.ICON_ERROR, caption="errore MD5")
                        errorMD5.ShowModal()
                n += 1
                if n >= self.gauge.GetRange():
                    self.gauge.Pulse()
                else:
                    self.gauge.SetValue(n)
        else:
            self.importDirError = 1
            dlg = wx.MessageDialog(self, "Directory Import Inesistente", style=wx.ICON_ERROR,
                                   caption="Directory Import Inesistente")
            dlg.ShowModal()


if __name__ == '__main__':
    # create logger
    logger = logging.getLogger('photoark')
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    #ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(msg)s)')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)


    # 'application' code
    # logger.debug('debug message')
    # logger.info('info message')
    # logger.warning('warn message')
    # logger.error('error message')
    # logger.critical('critical message')
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoManager")
    PhotoManagerApp.MainLoop()
