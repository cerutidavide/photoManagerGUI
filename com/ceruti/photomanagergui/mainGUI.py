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
#   IMAGEIO non legge qualcosa mentre exiftool legge tutto--> inutile usare IMAGEIO A REGIME per questa funzione (scrittura EXIF)
#   gestione input --> aggiungere date picker e time picker per adesso delta in ore e fisso
#   esempio >exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2
#   exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2

# ATTENZIONE se recycled_bin è incluso nel folder che sto processando con fixdate--LOOP INFINITO
# ATTENZIONE se restored è incluso nel backup stesso problema
# IMPOSTARE folder validi restore e backup ?
# TODO potrebbe avere senso salvare lista immagini non riconosciute

# TODO folder destinazione con il giorno
# TODO FORMATTAZIONE LOG
# TODO gestione immagini non riconosciute con Exiftool
# TODO valutare "con e senza exif tool"
# TODO conteggio Immagini non identificate e lista dei file non identificati da (eventualemente) pulire
# TODO LOG SU FILE
# TODO sistemare pulsanti e barre di avanzamento
# TODO EXIF SET GPS DATA ORA
# TODO valutare database per statistiche
# TODO valutare refactor "a oggetti" con vari moduli
# TODO Impacchettare appliczione
# TODO valutare/verificare multiplatform
# provare a pensare "immagini simili" e.g.  librerie AI di analisi immagini...

def LoadPropertiesAndInitArchive(basePath='c:\\Utenti\\Davide\\photoManagerGUI',
                                 filenameGlob="default.props", filenameMstr=".masterrepository.conf"):
    myHashGlob = {}
    myHashGlob['fileconfprincipale'] = filenameGlob
    myHashGlob['masterrepositoryconf'] = filenameMstr
    logger.debug(
        "File configurazione principale: %s\\%s Path PC aziendale: C:\\Users\\Davide\\PhotoManager Path PC Casa: C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master",
        basePath, filenameGlob)
    with open(os.path.join(basePath, filenameGlob), encoding="utf-8") as f:
        for line in f.readlines():
            match = re.search('^masterrepository=(.*)', line)
            if match:
                myHashGlob['masterrepository'] = match[1]
                logger.debug("Parametro letto nel file di configurazione: #masterrepository# %s", str(match[1]))
            match = re.search('^selectedfolder=(.*)', line)
            if match:
                myHashGlob['selectedfolder'] = match[1]
                logger.debug("Parametro letto nel file di configurazione #selectedfolder# " + str(match[1]))
        myHashGlob['masterrepository_bin'] = myHashGlob['masterrepository'] + "\\recycled-bin"
        myHashGlob['masterrepository_bak'] = myHashGlob['masterrepository'] + "\\backup"
        myHashGlob['masterrepository_work'] = myHashGlob['masterrepository'] + "\\work-area"
        myHashGlob['masterrepository_restore'] = myHashGlob['masterrepository'] + "\\restoredfiles"
        myHashGlob['masterrepository_originals'] = myHashGlob['masterrepository'] + "\\foto_originali"
        myHashGlob['masterrepository_lightroom'] = myHashGlob['masterrepository'] + "\\from_export_lightroom"
        myHashGlob['f_copia'] = dict()
        myHashGlob['f_copia']['copied'] = []
        myHashGlob['f_copia']['skipped'] = []
        myHashGlob['f_copia']['file_errors'] = []
        myHashGlob['f_copia']['tot_files'] = []
        myHashGlob['f_copia']['tot_dirs'] = []
        myHashGlob['f_copia']['importdir_error'] = []
        myHashGlob['f_listaestensioni'] = dict()
        myHashGlob['f_checkarchivio'] = dict()
        myHashGlob['f_checkarchivio']['tot_dirs'] = []
        myHashGlob['f_checkarchivio']['tot_files'] = []
        myHashGlob['f_checkarchivio']['duplicatedfiles_dict'] = dict()
        myHashGlob['f_fixdate'] = dict()
        myHashGlob['f_fixdate']['fixed'] = []
        myHashGlob['f_fixdate']['skipped'] = []
        myHashGlob['f_fixdate']['tot_files'] = []
        myHashGlob['f_fixdate']['tot_dirs'] = []
        myHashGlob['f_fixdate']['dstfolder'] = []
        myHashGlob['f_restore'] = dict()
        myHashGlob['f_restore']['tot_dirs'] = []
        myHashGlob['f_restore']['original-restored'] = []
        myHashGlob['f_restore']['original-duplicated'] = []
        myHashGlob['f_restore']['non-original-restored'] = []
        myHashGlob['f_restore']['non-original-duplicated'] = []
        myHashGlob['f_restore']['tot_files'] = []
        myHashGlob['f_restore']['reading_error_files'] = []
        myHashGlob['f_restore']['original-copyerrors'] = []
        myHashGlob['f_restore']['non-original-copyerrors'] = []
        myHashGlob['f_restore']['error_files'] = []
        myHashGlob['f_restore']['dstfolder'] = []
        myHashGlob['f_loadextension'] = dict()
        myHashGlob['f_loadextension']['root_folder'] = []
        myHashGlob['f_loadextension']['extension_list'] = []
    return myHashGlob


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title, *args, **kw):
        super().__init__(*args, **kw)
        wx.Panel.__init__(self, parent, title=title, size=(725, 700))

        # sizer = wx.BoxSizer(wx.VERTICAL)
        # sizer.Add(wx.Button(self, -1, 'An extremely long button text'), 0, 0, 0)
        # sizer.Add(wx.Button(self, -1, 'Small button'), 0, 0, 0)
        # sizer.
        # self.SetSizer(sizer)

        max_gauge_size = 700
        if (os.path.exists("C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master")):
            self.basePath = "C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master"
        if (os.path.exists("C:\\Users\\Davide\\PhotoManager")):
            self.basePath = "C:\\Users\\Davide\\PhotoManager"
        logger.debug('Path base impostato a %s ', self.basePath)
        self.baseFile = "default.props"
        logger.info(
            "File configurazione principale: %s\\%s Path PC aziendale: C:\\Users\\Davide\\PhotoManager Path PC Casa: C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master",
            self.basePath, self.baseFile)
        self.globpropsHash = LoadPropertiesAndInitArchive(self.basePath, self.baseFile, ".masterrepository.conf")
        logger.debug("Dict Parametri di configurazione ")
        for (k, v) in self.globpropsHash.items():
            logger.debug("Chiave: %s Valore: %s", str(k), str(v))
        logger.info('Archivio Fotografie: %s', self.globpropsHash['masterrepository'])
        self.gauge = wx.Gauge(self, pos=(5, 640), size=(max_gauge_size, -1))
        self.gauge.SetRange(max_gauge_size)
        self.gauge.SetValue(0)
        self.workingDirList = wx.GenericDirCtrl(self, pos=(5, 30), size=(345, 230), style=wx.DIRCTRL_DIR_ONLY)
        if 'selectedfolder' not in self.globpropsHash.keys():
            self.workingDirList.SetPath("c:\\temp")
            self.workingDirList.SelectPath("c:\\temp", select=True)
            self.globpropsHash['selectedfolder'] = "C:\\temp"
        else:
            self.workingDirList.SetPath(self.globpropsHash['selectedfolder'])
            self.workingDirList.SelectPath(self.globpropsHash['selectedfolder'], select=True)
        self.workingDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaWorkingDir)
        self.archivioFotografie = wx.StaticText(self, label="Archivio Fotografie Master: " + self.globpropsHash[
            'masterrepository'], pos=(5, 600))
        self.directoryCorrente = wx.StaticText(self, label="Cartella Selezionata per Azioni sulla destra: " +
                                                           self.globpropsHash['selectedfolder'], pos=(5, 5))
        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file Cartella Selezionata",
                                                    pos=(360, 30), size=(345, -1))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)
        self.avviaCopiaFile = wx.Button(self, label="Avvia Import In Archivio Master", pos=(360, 90), size=(345, -1))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.destinazioneCopia = wx.RadioBox(self, label="Destinazione Copia:", majorDimension=2,
                                             pos=(360, 120), size=(345, -1),
                                             choices=["Originals", "Export Lightroom"])
        self.modoCopia = wx.RadioBox(self, label="Azione Su File IMPORTATI/SKIPPATI:", majorDimension=3,
                                     pos=(360, 180), size=(345, -1),
                                     choices=["nessuna azione", "cestino archivio", "cestino windows"])
        self.avviaCheckArchivio = wx.Button(self, label="Avvia Controllo Duplicati Cartella Selezionata", pos=(360, 55),
                                            size=(345, -1))
        self.avviaCheckArchivio.Bind(wx.EVT_BUTTON, self.AvviaCheckArchivio)

        self.avviaFixDateTime = wx.Button(self, label="Avvia Fix Orario Cartella Selezionata", pos=(360, 240),
                                          size=(345, -1))
        self.avviaFixDateTime.Bind(wx.EVT_BUTTON, self.AvviaFixDateTime)
        self.modoFixData = wx.RadioBox(self, label="Attraversare Sotto Cartelle Sì/No", majorDimension=2,
                                       pos=(360, 280), size=(345, -1),
                                       choices=["Sì", "No"])
        self.avviaRestore = wx.Button(self, label="Avvia Restore file _original dal folder selezionato", pos=(360, 340),
                                      size=(345, -1))
        self.avviaRestore.Bind(wx.EVT_BUTTON, self.AvviaRestore)
        self.esci = wx.Button(self, label="ESCI", pos=(360, 550), size=(345, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)
        self.outputWindow = wx.TextCtrl(self, pos=(5, 280), size=(345, 300), style=wx.TE_MULTILINE)
        self.SetFocus()
        self.Center()
        self.Show(True)

    def fileDictShow(self, function='davide', shortFMT=False):
        outputmessage = ''
        riepilogo = ''
        logger.debug('Funzione da mostrare %s', function)
        if function in self.globpropsHash.keys():
            logger.debug('Funzione definita %s', function)
            riepilogo = 'Funzione: ' + function + '\n'
            for p in self.globpropsHash[function]:
                match = re.search('_dict', p)
                if match:
                    logger.debug('PARAMETRO %s è un dict', p)
                    outputmessage += '> ' + function + ' ' + p + ' elementi distinti: ' + str(
                        len(self.globpropsHash[function][p].keys())) + '\n'
                    riepilogo += p + '-file distinti: ' + str(len(self.globpropsHash[function][p].keys()))
                    for k, v in self.globpropsHash[function][p].items():
                        outputmessage += 'Chiave>> ' + k + ' >>Valore ' + str(v) + '\n'
                        logger.debug('****Funzione %s **** Parametro %s **** Chiave %s **** Valore %s', function, p,
                                     str(k), self.globpropsHash[function][p][k])
                    outputmessage += '\n'
                else:
                    n = len(self.globpropsHash[function][p])
                    outputmessage += '> ' + function + ' ' + p + ' (' + str(n) + ')\n'
                    riepilogo += p + ' ' + str(n) + '\n'
                    for v in self.globpropsHash[function][p]:
                        outputmessage += str(n) + ' >> ' + v + '\n'
                        logger.debug('****Funzione %s **** Parametro %s **** Valore %s', function, p, v)
                        n -= 1
                    outputmessage += '\n'
        else:
            logger.debug('****Funzione**** non definita %s', function)
            riepilogo = 'Impossibile mostrare output funzione eseguita'
        if shortFMT:
            return riepilogo
        return outputmessage + riepilogo

    def CleanConfigFunction(self):
        logger.debug('Scorro dict di configurazione')
        for k in self.globpropsHash.keys():
            if str(k).startswith('f_'):
                logger.debug('Funzione: %s', str(k))
                for c in self.globpropsHash[k].keys():
                    logger.debug('Nome Dict Da Cancellare [%s][%s], Numero elementi da Cancellare  %s', str(k), str(c),
                                 str(len(self.globpropsHash[k][c])))
                    self.globpropsHash[k][c].clear()
                    logger.debug('Dict Svuotato [%s][%s] Valore %s', str(k), str(c), str(self.globpropsHash[k][c]))
            else:
                logger.debug('Parametro generale: %s Valore: %s', str(k), str(self.globpropsHash[k]))

    def fileTS(self):
        return str(datetime.now()).replace(' ', '_').replace(':', '_').replace('-', '_') + '_'

    def SelezionaWorkingDir(self, evt):
        if self.workingDirList.GetPath():
            self.globpropsHash['selectedfolder'] = self.workingDirList.GetPath()
        self.directoryCorrente.SetLabel(
            "Cartella Selezionata per Azioni sulla destra: " + self.globpropsHash['selectedfolder'])

    def AvviaCaricaEstensioni(self, evt):
        self.gauge.SetValue(0)
        self.CleanConfigFunction()
        self.CaricaEstensioni(self.globpropsHash['selectedfolder'], True)
        self.gauge.SetValue(self.gauge.GetRange())
        okCheck = wx.MessageDialog(self, self.fileDictShow('f_loadextension', True), style=wx.ICON_INFORMATION,
                                   caption="Esecuzione Lista Estensioni Terminata")
        okCheck.ShowModal()
        self.outputWindow.SetValue(self.fileDictShow('f_loadextension'))
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def CaricaEstensioni(self, dir="/tmp/", firstcall=True):
        if firstcall is True:
            logger.debug('Prima esecuzione Carica Estensioni radice: %s', str(dir))
            self.globpropsHash['f_loadextension']['extension_list'] = []
            logger.info('Lista estensione inizializzata vuota %s', str(dir))
            self.globpropsHash['f_loadextension']['root_folder'] = [str(dir)]
        try:
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    self.CaricaEstensioni(file, False)
                else:
                    ext = pathlib.Path(file).suffix
                    logger.debug('Trovata estensione %s: ', str(ext))
                    if ext not in self.globpropsHash['f_loadextension']['extension_list']:
                        self.globpropsHash['f_loadextension']['extension_list'].append(ext)
                        logger.info('Aggiunta estensione %s', str(ext))
                    else:
                        logger.debug('Non aggiunta estensione %s, già presente: ', str(ext))
                    self.gauge.SetValue(self.gauge.GetValue() + 1)
                    if self.gauge.GetValue() >= self.gauge.GetRange():
                        self.gauge.SetValue(0)
        except Exception as e:
            logger.error('Errore ricerca file o directory %s', str(e))

    def Esci(self, evt):
        self.Close()
        pass

    def AvviaRestore(self, evt):
        self.CleanConfigFunction()
        self.globpropsHash['f_restore']['dstfolder'] = [self.fileTS()]
        self.Restore(self.globpropsHash['selectedfolder'], False)
        self.gauge.SetValue(self.gauge.GetRange())
        okCheck = wx.MessageDialog(self, self.fileDictShow('f_restore', True), style=wx.ICON_INFORMATION,
                                   caption="Restore Terminata")
        okCheck.ShowModal()
        self.outputWindow.SetValue(self.fileDictShow('f_restore'))
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def Restore(self, dir="C:\\Users\\c333053\\TestImport", dirrecursion=False):
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_restore']['tot_dirs']))
            logger.debug("<<<INIZIO CARTELLA %s >>>", dir)
            self.globpropsHash['f_restore']['tot_dirs'].append(dir)
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    logger.debug("DIRECTORY %s <ATTRAVERSO LA DIRECTORY> %s", id_log_counter_dir, file.path)
                    self.Restore(file.path, True)
                else:
                    id_log_counter = str(len(self.globpropsHash['f_restore']['tot_files']))
                    logger.debug("FILE %s_%s %s <Inizio", id_log_counter_dir, id_log_counter, file.path)
                    self.globpropsHash['f_restore']['tot_files'].append(file.path)
                    try:
                        fmd5 = open(file, "rb")
                        logger.debug("FILE %s_%s %s <Aperto>", id_log_counter_dir, id_log_counter, file.path)
                        match = re.search('.*_(.*)\.', str(file.name))
                        if match:
                            logger.debug("FILE %s_%s <md5 ricavato nome file> %s", id_log_counter_dir, id_log_counter,
                                         match[1])
                            read_md5filename = match[1] + pathlib.Path(file).suffix.replace('_original', '')
                            calculated_md5filename = hashlib.file_digest(fmd5, "md5").hexdigest() + pathlib.Path(
                                file).suffix.replace('_original', '')

                        else:
                            logger.debug("FILE %s_%s <Il file  %s non presenta la struttura di un file di backup ",
                                         id_log_counter_dir, id_log_counter, file.name)
                            calculated_md5filename = hashlib.file_digest(fmd5, "md5").hexdigest() + pathlib.Path(
                                file).suffix
                            read_md5filename = file.name
                        dstfolder = self.globpropsHash['masterrepository_restore'] + '\\' + \
                                    self.globpropsHash['f_restore']['dstfolder'][0]
                        dstfolder_original = dstfolder + '\\originals\\'
                        dstfolder_non_original = dstfolder + '\\non_originals\\'
                        logger.debug("FOLDER Destinazione RESTORE %s ", dstfolder)
                        if not os.path.exists(dstfolder):
                            os.makedirs(dstfolder)
                            logger.debug("FOLDER Destinazione RESTORE %s CREATA ", dstfolder)
                        if not os.path.exists(dstfolder_original):
                            os.makedirs(dstfolder_original)
                            logger.debug("FOLDER Destinazione RESTORE %s CREATA ", dstfolder_original)
                        if not os.path.exists(dstfolder_non_original):
                            os.makedirs(dstfolder_non_original)
                            logger.debug("FOLDER Destinazione RESTORE %s CREATA ", dstfolder_non_original)
                        logger.debug("FILE %s %s  <file name con md5 calcolato> %s <file name preso dal nomefile> %s ",
                                     str(id_log_counter_dir), str(id_log_counter), calculated_md5filename,
                                     read_md5filename)
                        if (calculated_md5filename == read_md5filename):
                            logger.debug("FILE %s %s  <MD5 MATCH per il file %s ", str(id_log_counter_dir),
                                         str(id_log_counter), file.name)
                            logger.info("FILE %s %s  <FILE ORIGINALE DA RESTORARE %s ", str(id_log_counter_dir),
                                        str(id_log_counter), file.name)
                            dstfile = dstfolder_original + calculated_md5filename
                            try:
                                if not (os.path.exists(dstfile)):
                                    shutil.copy2(file, dstfile)
                                    self.globpropsHash['f_restore']['original-restored'].append(dstfile)
                                    logger.info('File RESTORATO DA COMPLETARE')
                                else:
                                    self.globpropsHash['f_restore']['original-duplicated'].append(file.path)
                            except IOError as eio:
                                logger.error("FILE %s %s  <Problemi nell'estrazione del file %s errore: %s",
                                             str(id_log_counter_dir), str(id_log_counter), file.path, str(eio))
                                self.globpropsHash['f_restore']['original-copyerrors'].append(file.path)
                        else:
                            dstfile = dstfolder_non_original + calculated_md5filename
                            try:
                                if not (os.path.exists(dstfile)):
                                    shutil.copy2(file, dstfile)
                                    self.globpropsHash['f_restore']['non-original-restored'].append(dstfile)
                                else:
                                    self.globpropsHash['f_restore']['non-original-duplicated'].append(file.path)
                            except IOError as eio:
                                logger.error("FILE %s %s  <Problemi nella copia del file %s errore: %s",
                                             str(id_log_counter_dir), str(id_log_counter), file.path, str(eio))
                                self.globpropsHash['f_restore']['non-original-copyerrors'].append(file.path)
                            logger.debug("FILE %s %s  <MD5 NO MATCH per il file %s ", str(id_log_counter_dir),
                                         str(id_log_counter), file.name)
                            logger.info(
                                "FILE %s %s  <FILE CON METADATI MODIFICATI RISPETTO AL FILE ORIGINALE DA RESTORARE %s ",
                                str(id_log_counter_dir), str(id_log_counter), file.path)

                        fmd5.close()
                        logger.debug(
                            "FILE " + str(id_log_counter_dir) + "_" + str(id_log_counter) + " <è un file...> " + str(
                                file.path) + " LO CHIUDO")
                    except FileNotFoundError as e:
                        logger.error("<<ERRORE APERTURA FILE: %s ", file.path)
                        self.globpropsHash['f_restore']['reading_error_files'].append(file.path)
            dir_iterator.close()
            logger.info("<<<FINE CARTELLA>>> <<< %s >>>", dir)

    def AvviaFixDateTime(self, evt):
        self.CleanConfigFunction()
        self.globpropsHash['f_fixdate']['dstfolder'] = [self.fileTS()]
        self.FixDateTime(self.globpropsHash['selectedfolder'], False)
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.fileDictShow('f_fixdate'))
        okCheck = wx.MessageDialog(self, self.fileDictShow('f_fixdate', True), style=wx.ICON_INFORMATION,
                                   caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def FixDateTime(self, dir="C:\\Users\\c333053\\TestImport", dirrecursion=False):
        self.fixmode = self.modoFixData.GetSelection()
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_fixdate']['tot_dirs']))
            logger.info("<<<INIZIO CARTELLA %s >>>", dir)
            self.globpropsHash['f_fixdate']['tot_dirs'].append(dir)
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    if self.fixmode == 1:
                        logger.debug("DIRECTORY %s <NON ATTRAVERSO LA DIRECTORY> %s", id_log_counter_dir,
                                     str(file.path))
                    else:
                        logger.debug("DIRECTORY %s <ATTRAVERSO LA DIRECTORY> %s", id_log_counter_dir, str(file.path))
                        self.FixDateTime(str(file.path), True)
                else:
                    id_log_counter = str(len(self.globpropsHash['f_fixdate']['tot_files']))
                    logger.debug("FILE %s_%s <INIZIO> %s", id_log_counter_dir, id_log_counter, file.path)
                    with exiftool.ExifTool() as et:
                        # Al momento fisso a +7 ore
                        deltaDateTime = '00:00:00 07:00:00'
                        exiftoolModDatePar = '-ModifyDate+=\"' + deltaDateTime + '\"'
                        exiftoolCreateDatePar = '-CreateDate+=\"' + deltaDateTime + '\"'
                        exiftoolOrigDatePar = '-DateTimeOriginal+=\"' + deltaDateTime + '\"'
                        logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ", id_log_counter_dir,
                                     id_log_counter, exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar)
                        try:
                            et.execute(exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar, file.path)
                            srcbckfullfilename = file.path + '_original'
                            dstbckfilename = file.name + '_original'
                            dstbckfoldername = self.globpropsHash['masterrepository_bak'] + '\\' + \
                                               self.globpropsHash['f_fixdate']['dstfolder'][0]
                            dstbckfullfilename = dstbckfoldername + '\\' + str(datetime.now()).replace(' ',
                                                                                                       '_').replace(':',
                                                                                                                    '_').replace(
                                '-', '_') + '_' + dstbckfilename
                            logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ", id_log_counter_dir,
                                         id_log_counter, exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar)
                            logger.debug("FILE %s_%s <STDOUT CMD EXIFTOOL %s > ", id_log_counter_dir, id_log_counter,
                                         str(et.last_stdout).replace('\n', ''))
                            logger.debug("FILE %s_%s <STDERR CMD EXIFTOOL %s > ", id_log_counter_dir, id_log_counter,
                                         str(et.last_stderr))
                            logger.debug("FILE %s_%s <RISULTATO CMD EXIFTOOL %s", id_log_counter_dir, id_log_counter,
                                         str(et.last_status))
                            if et.last_status == 0 and et.last_stdout.rfind('unchanged') < 0:
                                logger.debug("FILE %s_%s <SRC: %s> <DST: %s>", id_log_counter_dir, id_log_counter,
                                             srcbckfullfilename, dstbckfullfilename)
                                self.globpropsHash['f_fixdate']['fixed'].append(str(file.path))
                                if not os.path.exists(dstbckfoldername):
                                    os.makedirs(dstbckfoldername)
                                shutil.move(srcbckfullfilename, dstbckfullfilename, copy_function='copy2')
                                logger.info("FILE %s_%s <Data-Ora Aggiornata> %s", id_log_counter_dir, id_log_counter,
                                            file.path)
                            else:
                                logger.error("<<PROBLEMA ESECUZIONE EXIF su file: %s ", str(file.path))
                                self.globpropsHash['f_fixdate']['skipped'].append(str(file.path))
                        except IOError as e:
                            logger.error("<<ERRORE SPOSTAMENTO FILE BACKUP: %s su %s ", srcbckfullfilename,
                                         dstbckfullfilename)
                        self.globpropsHash['f_fixdate']['tot_files'].append(str(file.path))
            dir_iterator.close()
            logger.info("<<<FINE CARTELLA>>> <<< %s >>>", dir)

    def AvviaCheckArchivio(self, evt):
        self.CleanConfigFunction()
        self.CheckArchivio(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.fileDictShow('f_checkarchivio'))
        okCheck = wx.MessageDialog(self, self.fileDictShow('f_checkarchivio', True), style=wx.ICON_INFORMATION,
                                   caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def CheckArchivio(self, dir="C:\\Users\\c333053\\TestImport"):
        self.globpropsHash['f_checkarchivio']['tot_dirs'].append(dir)
        id_log_counter_dir = len(self.globpropsHash['f_checkarchivio']['tot_dirs'])
        self.gauge.SetValue(len(self.globpropsHash['f_checkarchivio']['tot_files']))
        if os.path.exists(dir):
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                id_log_counter = len(self.globpropsHash['f_checkarchivio']['tot_files'])
                if file.is_dir():
                    logger.debug("FILE %s_%s <è una directory> %s", id_log_counter_dir, id_log_counter, str(file.path))
                    self.CheckArchivio(str(file.path))
                else:
                    logger.debug("FILE %s_%s  <APERTURA FILE> %s", id_log_counter_dir, id_log_counter, str(file.path))
                    try:
                        with open(file, "rb") as fmd5:
                            md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()
                            logger.debug("FILE %s_%s <md5 calcolato> %s", id_log_counter_dir, id_log_counter,
                                         md5filename)
                            try:
                                if md5filename not in self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict']:
                                    self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][md5filename] = [
                                        file.path]
                                    logger.debug("FILE %s_%s <Inserimento nuovo file> chiave: %s valore %s",
                                                 id_log_counter_dir, id_log_counter, md5filename, str(
                                            self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][md5filename]))
                                    logger.info("FILE %s_%s <Inserimento nuovo file> chiave: %s valore %s",
                                                id_log_counter_dir, id_log_counter, md5filename, str(
                                            self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][md5filename]))
                                else:
                                    self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][md5filename].append(
                                        file.path)
                                    logger.debug('FILE %s_%s <Aggiunto duplicato> <k,v> chiave: %s, valore: %s',
                                                 id_log_counter_dir, id_log_counter, md5filename,
                                                 self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][
                                                     md5filename])
                                    logger.info('FILE %s_%s <Aggiunto duplicato> <k,v> chiave: %s, valore: %s',
                                                id_log_counter_dir, id_log_counter, md5filename,
                                                self.globpropsHash['f_checkarchivio']['duplicatedfiles_dict'][
                                                    md5filename])
                            except KeyError as ke:
                                logger.error('ERRORE CHIAVE errore: %s', str(ke))
                            fmd5.close()
                    except IOError as eio:
                        logger.error('ERRORE FILE errore %s', str(eio))
                    logger.debug("FILE %s_%s <CHIUSURA FILE> %s", id_log_counter_dir, id_log_counter, str(file.path))
                    self.globpropsHash['f_checkarchivio']['tot_files'].append(file.path)
                    self.gauge.SetValue(len(self.globpropsHash['f_checkarchivio']['tot_files']))
            dir_iterator.close()
            logger.debug("<<< %s >>> %s <<<FINE CARTELLA>>>", str(dir), id_log_counter_dir)

    def AvviaCopiaFile(self, evt):
        self.CleanConfigFunction()
        self.CopiaFile(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.fileDictShow('f_copia'))
        okCheck = wx.MessageDialog(self, self.fileDictShow('f_copia', True), style=wx.ICON_INFORMATION,
                                   caption="Copia Terminata")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def CopiaFile(self, dir="C:\\Users\\c333053\\TestImport"):
        id_log_counter_dir = len(self.globpropsHash['f_copia']['tot_dirs'])
        if os.path.exists(dir):
            logger.info("FILE %s <Apertura Cartella> %s", id_log_counter_dir, dir)
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                id_log_counter_file = len(self.globpropsHash['f_copia']['tot_files'])
                if file.is_dir():
                    self.globpropsHash['f_copia']['tot_dirs'].append(file.path)
                    logger.debug("FILE %s_ <è una directory> %s", str(id_log_counter_dir), file.path)
                    self.CopiaFile(file.path)
                else:
                    logger.debug("FILE %s_%s <è un file> %s Lo apro", str(id_log_counter_dir), str(id_log_counter_file),
                                 file.path)
                    self.globpropsHash['f_copia']['tot_files'].append(file.path)
                    try:
                        with open(file, "rb") as fmd5:
                            md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()
                            logger.debug("FILE %s_%s <md5 calcolato> %s", str(id_log_counter_dir),
                                         str(id_log_counter_file), md5filename)
                            fmd5.close()
                            logger.debug("FILE %s_%s <è un file> %s Lo chiudo", str(id_log_counter_dir),
                                         str(id_log_counter_file), file.path)
                        srcfile = os.fsdecode(file)
                        logger.debug('Destinazione copia impostata su %s', self.destinazioneCopia.GetSelection())
                        if self.destinazioneCopia.GetSelection() == 0:
                            dstroot = self.globpropsHash['masterrepository_originals']
                        if self.destinazioneCopia.GetSelection() == 1:
                            dstroot = self.globpropsHash['masterrepository_lightroom']
                        dstcamerafolder = "ProduttoreNonNoto\\ModelloNonNoto"
                        dstmaker = 'ProduttoreNonNoto'
                        dstmodel = 'ModelloNonNoto'
                        dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                        dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                        dstdayfolder = time.strftime("%d", time.gmtime(os.path.getmtime(file)))
                        logger.debug('Cartella Giorno: day: %s', dstdayfolder)
                        dstext = os.path.splitext(file)[1].lower()
                        try:
                            with Image.open(pathlib.Path(file)) as image:
                                info = image.getexif()
                                if info:
                                    logger.debug("FILE %s_%s <ha exif tags> %s ", str(id_log_counter_dir),
                                                 str(id_log_counter_file), file.path)
                                    for (tag, value) in info.items():
                                        decoded = TAGS.get(tag, tag)
                                        logger.debug("FILE %s_%s <EXIF_TAG> %s <DECODED_TAG> %s TAG_VALUE: ",
                                                     str(id_log_counter_dir), str(id_log_counter_file), str(tag),
                                                     TAGS.get(tag, tag)), str(info[tag])
                                        if decoded == 'DateTime':
                                            logger.debug("FILE %s_%s <Anno/Mese da DataFile:> %s / %s ",
                                                         str(id_log_counter_dir), str(id_log_counter_file),
                                                         dstyearfolder, dstmonthfolder)
                                            dstyearfolder = time.strftime("%Y",
                                                                          time.strptime(value, "%Y:%m:%d %H:%M:%S"))
                                            dstmonthfolder = time.strftime("%m",
                                                                           time.strptime(value, "%Y:%m:%d %H:%M:%S"))
                                            dstdayfolder = time.strftime("%d",
                                                                         time.strptime(value, "%Y:%m:%d %H:%M:%S"))
                                            logger.debug("FILE %s_%s <Anno/Mese da DataFile:> %s / %s ",
                                                         str(id_log_counter_dir), str(id_log_counter_file),
                                                         dstyearfolder, dstmonthfolder)
                                        if decoded == 'Make' and value != '':
                                            dstmaker = value.strip().replace(' ', '')
                                            dstcamerafolder = dstmaker
                                            logger.debug("FILE %s_%s <PRODUTTORE:> %s", str(id_log_counter_dir),
                                                         str(id_log_counter_file), dstmaker)
                                        if decoded == 'Model' and value != '':
                                            dstmodel = value.strip().replace(' ', '-')
                                            logger.debug("FILE %s_%s <MODELLO:> %s", str(id_log_counter_dir),
                                                         str(id_log_counter_file), dstmodel)
                                    dstcamerafolder = dstmaker + "\\" + dstmodel
                                    logger.debug("FILE %s_%s <FOTOCAMERA:> %s", str(id_log_counter_dir),
                                                 str(id_log_counter_file), dstcamerafolder)
                        except UnidentifiedImageError as ime:
                            logger.error("Immagine Non identificata %s errore: %s", file.path, str(ime))
                        dstfolder = dstroot + "\\" + dstcamerafolder + "\\" + dstyearfolder + "\\" + dstmonthfolder + "\\" + dstdayfolder
                        dstfile = dstfolder + "\\" + md5filename + dstext
                        logger.debug("FILE %s_%s <Destinazione individuata:> %s", str(id_log_counter_dir),
                                     str(id_log_counter_file), dstfile)
                        logger.debug("FILE %s_%s <CopyMode:> %s", str(id_log_counter_dir), str(id_log_counter_file),
                                     str(self.destinazioneCopia.GetSelection()))
                        if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                            os.makedirs(self.globpropsHash['masterrepository_bin'])
                            logger.debug("FOLDER_CESTINO_ARCHIVIO: %s", self.globpropsHash['masterrepository_bin'])
                        if not os.path.exists(dstfolder):
                            os.makedirs(dstfolder)
                        if not os.path.exists(dstfile):
                            logger.debug("File: %s Non Esiste, lo copio", dstfile)
                            try:
                                shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                                logger.info("FILE %s_%s <File Copiato> %s su %s", str(id_log_counter_dir),
                                            str(id_log_counter_file), srcfile, dstfile)
                                self.globpropsHash['f_copia']['copied'].append(file.path)
                                if self.modoCopia.GetSelection() == 1:
                                    try:
                                        shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                                    copy_function='copy2')
                                    except IOError as e:
                                        logger.error("<<ERRORE SPOSTAMENTO FILE:>>File: %s su %s errore: %s", srcfile,
                                                     dstfile, str(e))
                                if self.modoCopia.GetSelection() == 2:
                                    try:
                                        send2trash(srcfile)
                                    except IOError as e:
                                        logger.error("<<ERRORE CESTINO:>>File: %s errore: %s", srcfile, str(e))
                            except IOError as e:
                                logger.error("<<ERRORE COPIA>>File: %s su %s errore: %s", srcfile, dstfile, str(e))
                        else:
                            if self.modoCopia.GetSelection() == 1:
                                try:
                                    shutil.move(srcfile, self.globpropsHash['masterrepository_bin'],
                                                copy_function='copy2')
                                except IOError as e:
                                    logger.error("<<ERRORE SPOSTAMENTO>>File: %s su %s errore: %s", srcfile, dstfile,
                                                 str(e))
                            if self.modoCopia.GetSelection() == 2:
                                try:
                                    send2trash(srcfile)
                                except IOError as e:
                                    logger.error("<<ERRORE CESTINO:>>File: %s errore: %s", srcfile, str(e))
                            logger.info("FILE %s_%s <File Skipped> %s su %s", str(id_log_counter_dir),
                                        str(id_log_counter_file), srcfile, dstfile)
                            self.globpropsHash['f_copia']['skipped'].append(file.path)
                    except Exception as er:
                        self.globpropsHash['f_copia']['file_errors'].append(file.path)
                        logger.error('Errore nell \'apertura del file %s errore: %s', file.path, str(er))
            logger.info("FILE %s <Chiusura Cartella> %s", id_log_counter_dir, dir)
            dir_iterator.close()
        else:
            dlg = wx.MessageDialog(self, "Directory Import Inesistente", style=wx.ICON_ERROR,
                                   caption="Directory Import Inesistente")
            dlg.ShowModal()


if __name__ == '__main__':
    logger = logging.getLogger('photoark')
    stdout = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - [%(lineno)s-%(funcName)s()] %(message)s")
    stdout.setFormatter(fmt)
    logger.addHandler(stdout)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.debug('Inizializzazione LOG completa')
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoManager")
    PhotoManagerApp.MainLoop()
