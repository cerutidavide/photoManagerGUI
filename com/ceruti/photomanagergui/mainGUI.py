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
# TODO modificare alberatura per gestire modello MACCHINA FOTOGRAFICA
# TODO LOG SU FILE
# TODO CONTROLLO PERMESSI
# TODO sistemare pulsanti e barre di avanzamento
# TODO riorganizzare interfaccia grafica
# TODO EXIF SISTEMAZIONE DATA ORA
# TODO EXIF SET GPS DATA ORA
# TODO LIBRERIA PYTHON MD5 al posto dell'esecuzione del comando esterno



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
                        logging.debug("Aggiunta " + ext[1] + " alla lista delle estensioni")
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
    logging.debug("<<Parametro impostato #file_di_configurazione_principale# "+os.path.join(workingdir, filenameGlob))
    myHashGlob['masterrepositoryconf'] = filenameMstr
    logging.debug("<<Parametro impostato #masterrepositoryconf# "+filenameMstr)
    with open(os.path.join(workingdir, filenameGlob), encoding="utf-8") as f:
        for line in f.readlines():
            # print(line)
            match = re.search('^masterrepository=(.*)', line)
            # print(match)
            if match:
                myHashGlob['masterrepository'] = match[1]
                logging.debug("<<Parametro letto nel file #masterrepository# " + str(match[1]))
            match = re.search('^importfolder=(.*)', line)
            if match:
                myHashGlob['importfolder'] = match[1]
                logging.debug("<<Parametro letto nel file #importfolder# " + str(match[1]))
            match = re.search('^importfilelist=(.*)', line)
            if match:
                myHashGlob['importfilelist'] = match[1]
                logging.debug("<<Parametro letto nel file #importfilelist# " + str(match[1])+"\n")
    return myHashGlob


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title):
        logging.root.setLevel('DEBUG')
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        max_gauge_size = 675
        self.checkRunning = True
        self.basePath="C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master"
        #self.basePath="C:\\Users\\Davide\\PhotoManager"
        self.baseFile="default.props"
        logging.info("###PARAMETRO FILE BASE### "+self.basePath+"\\"+self.baseFile+"\n")
        logging.info("###MODIFICARE basePath PER AZIENDALE: C:\\Users\\Davide\\PhotoManager ###")
        logging.info("###MODIFICARE basePath PER PC CASA:   C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master ###\n")
        self.globpropsHash=CheckAndLoadProperties(self.basePath,self.baseFile,".masterrepository.conf")
        #self.globpropsHash = CheckAndLoadProperties("C:\\Users\\Davide\\PhotoManager", "default.props",".masterrepository.conf")
        logging.info("###PARAMETRI DI CONFIGURAZIONE###  \n"+str(self.globpropsHash))
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
        print("**********   " + self.globpropsHash['importfolder'])
        self.SelezionaImportFolder(evt)
        print("**********   " + self.globpropsHash['importfolder'])
        messaggioEstensioni = str(loadFileExtensionList(self, self.globpropsHash['importfolder'], True))
        messaggioFolderImport = self.globpropsHash['importfolder']
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension = wx.MessageBox(
            "Nel folder import " + messaggioFolderImport + "\nci sono i seguenti tipi di file: \n" + messaggioEstensioni,
            '', wx.CLOSE)
        logging.info(messaggioEstensioni)

        self.gauge.SetValue(0)

    def TestExif(self, evt):
        for file in os.scandir(self.globpropsHash['importfolder']):
            if file.is_dir():
                logging.info("DIR: " + str(file.path))
            else:
                logging.debug("FILE: " + str(file.path))
                logging.debug('MODIFIED Datetime: ' + time.ctime(os.path.getmtime(file)))
                logging.debug('CREATED Datetime: ' + time.ctime(os.path.getctime(file)))
                with Image.open(pathlib.Path(file)) as image:
                    try:
                        exifData = {}
                        info = image.getexif()
                        if info:
                            for (tag, value) in info.items():
                                decoded = TAGS.get(tag, tag)
                                exifData[decoded] = value
                                logging.debug(image.filename + ' EXIF_TAG: ' + str(decoded) + ' ' + str(value))
                                if decoded == 'DateTime':
                                    logging.info(
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
                logging.debug("FILE CORRENTE>>>>>" + str(file.path))
                if file.is_dir():
                    logging.debug("CopiaFile.DIR: " + str(file.path))
                    self.CopiaFile(file, n)
                else:
                    logging.debug("CopiaFile.FILE: " + str(file.path))
                    md5command = 'certutil -hashfile \"' + str(file.path) + '\" MD5'
                    logging.debug(md5command)
                    #SEZIONE PROVA CALCOLO MD5 senza esecuzione comando
                    with open(file, "rb") as fmd5:
                        digest = hashlib.file_digest(fmd5, "md5")
                        logging.debug(digest.hexdigest())
                    #SEZIONE PROVA CALCOLO MD5 senza esecuzione comando
                    p = subprocess.run(md5command, shell=True, universal_newlines=True, stdout=subprocess.PIPE)
                    if p.returncode == 0:
                        srcfile = os.fsdecode(file)
                        dstroot = self.globpropsHash['masterrepository']
                        logging.debug("File Sorgente: " + srcfile)
                        dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                        dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                        md5filename = str(p.stdout).split('\n')[1]
                        dstext = os.path.splitext(file)[1].lower()
                        logging.debug("<md5filename> "+md5filename)
                        logging.debug("<ext> "+dstext)
                        logging.debug("FILE: " + str(file.path))
                        self.fileCounter['tot_files'] = self.fileCounter['tot_files'] + 1
                        try:
                            with Image.open(pathlib.Path(file)) as image:
                                try:
                                    exifData = {}
                                    info = image.getexif()
                                    if info:
                                        logging.debug("info EXIF non è nullo")
                                        for (tag, value) in info.items():
                                            decoded = TAGS.get(tag, tag)
                                            exifData[decoded] = value
                                            logging.debug(
                                                image.filename + ' EXIF_TAG: ' + str(decoded) + ' ' + str(value))
                                            if decoded == 'DateTime':
                                                logging.debug("FILE: " + str(
                                                    file.path) + " FILE_Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)
                                                logging.debug('EXIF DateTime: ' + time.asctime(
                                                    time.strptime(value, "%Y:%m:%d %H:%M:%S")))
                                                logging.debug('EXIF Presente Anno_PRE:' + dstyearfolder)
                                                logging.debug('EXIF Presente Mese_PRE:' + dstmonthfolder)
                                                dstyearfolder = time.strftime("%Y",
                                                                              time.strptime(value, "%Y:%m:%d %H:%M:%S"))
                                                dstmonthfolder = time.strftime("%m", time.strptime(value,
                                                                                                   "%Y:%m:%d %H:%M:%S"))
                                                logging.debug('EXIF Presente Anno_POST:' + dstyearfolder)
                                                logging.debug('EXIF Presente Mese_POST:' + dstmonthfolder)
                                                logging.debug("FILE: " + str(
                                                    file.path) + " EXIF_Nuovo Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)
                                    tiffDateTime=image.tag[306]
                                    logging.debug(tiffDateTime[0])
                                    logging.debug("DateTime tipo TIF non è nullo")
                                    logging.debug("FILE: " + str(file.path) + " FILE_Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)
                                    logging.debug('TIF DateTime: ' + time.asctime(time.strptime(tiffDateTime[0], "%Y:%m:%d %H:%M:%S")))
                                    logging.debug('TIF Presente Anno_PRE:' + dstyearfolder)
                                    logging.debug('TIF Presente Mese_PRE:' + dstmonthfolder)
                                    dstyearfolder = time.strftime("%Y",time.strptime(tiffDateTime[0], "%Y:%m:%d %H:%M:%S"))
                                    dstmonthfolder = time.strftime("%m", time.strptime(tiffDateTime[0],"%Y:%m:%d %H:%M:%S"))
                                    logging.debug('TIF Presente Anno_POST:' + dstyearfolder)
                                    logging.debug('TIF Presente Mese_POST:' + dstmonthfolder)
                                    logging.debug("FILE: " + str(
                                        file.path) + " TIF_Nuovo Anno/Mese: " + dstyearfolder + "/" + dstmonthfolder)

                                except BaseException as e:
                                    pass
                                    logging.error("ERRORONE")
                                    logging.error(str(e))
                                    logging.debug("info EXIF è nullo")
                        except UnidentifiedImageError:
                            logging.error("Immagine Non identificata")

                        dstfile = dstroot + "\\" + dstyearfolder + "\\" + dstmonthfolder + "\\" + md5filename + dstext
                        logging.debug("File Destinazione: " + dstfile)
                        self.globpropsHash['masterrepository_bin'] = self.globpropsHash[
                                                                         'masterrepository'] + "\\cestino"
                        self.copymode = self.modoCopia.GetSelection()
                        logging.debug("SELEZIONE BOTTONE: " + str(self.copymode))
                        if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                            os.makedirs(self.globpropsHash['masterrepository_bin'])
                            logging.debug("FOLDER_CESTINO_ARCHIVIO:" + self.globpropsHash['masterrepository_bin'])
                        if not os.path.exists(dstroot + "\\" + dstyearfolder + "\\" + dstmonthfolder):
                            os.makedirs(dstroot + "\\" + dstyearfolder + "\\" + dstmonthfolder)
                        if not os.path.exists(dstfile):
                            logging.debug("File: " + dstfile + " Non Esiste, lo copio")
                            try:
                                shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                                logging.info("<<COPIATO>>File: " + srcfile + " su " + dstfile)
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
                            logging.info("<<SKIPPED>>File: " + srcfile + " identico a " + md5filename + dstext)
                            self.fileCounter['skipped_files'] = self.fileCounter['skipped_files'] + 1
                    else:
                        logging.debug("Errore nel file: " + str(file.path))
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
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoManager")
    PhotoManagerApp.MainLoop()
