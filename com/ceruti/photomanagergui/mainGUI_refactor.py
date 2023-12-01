import datetime
import hashlib
import logging
import os
import pathlib
import re
import shutil
import time
from datetime import datetime

import exifread
import exiftool
import wx
import wx.dataview
from PIL import UnidentifiedImageError
from pathvalidate import ValidationError, validate_filepath
from send2trash import send2trash


# NB per cambiare tra pc aziendale e di casa basta commentre/scommentare dove va in errore
# NB pip install --proxy http://user:password@proxy.dominio.it:porta wxPython
#   IMAGEIO non legge qualcosa mentre exiftool legge tutto--> inutile usare IMAGEIO A REGIME per questa funzione (scrittura EXIF)
#   gestione input --> aggiungere date picker e time picker per adesso delta in ore e fisso
#   esempio >exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2
#   exiftool "-ModifyDate+=5:10:2 10:48:0" "-CreateDate+=5:10:2 10:48:0" "-DateTimeOriginal+=5:10:2 10:48:0" 00ce786eba035fc254739a7f54bb2867.cr2
# CREA LISTA trascura sempre tutti i file _original nella lista di file da trattare e ne crea una lista "da spostare" le altre procedure, prima di partire spostano i file con una procedura ad hoc che sposta i file _original sotto backup_timestamp aggiungeno n ad ogni copia del file con lo stesso nome
# TODO potrebbe avere senso salvare lista immagini non riconosciute
# TODO gestione immagini non riconosciute con Exiftool
# TODO valutare "con e senza exif tool"
# TODO conteggio Immagini non identificate e lista dei file non identificati da (eventualemente) pulire
# TODO sistemare pulsanti e barre di avanzamento
# TODO EXIF SET GPS DATA ORA
# TODO valutare database per statistiche
# TODO valutare refactor "a oggetti" con vari moduli
# TODO Impacchettare appliczione
# TODO valutare/verificare multiplatform
# TODO provare a pensare "immagini simili" e.g.  librerie AI di analisi immagini...


def load_properties_and_init_archive(base_path='c:\\Utenti\\Davide\\photoManagerGUI',
                                     filename_glob="default.props", filename_mstr=".masterrepository.conf"):
    my_hash_glob = {'fileconfprincipale': filename_glob, 'masterrepositoryconf': filename_mstr}

    logger.debug(
        f"File configurazione principale: {os.path.join(base_path, filename_glob)} "
        f"Path PC aziendale: C:\\Users\\Davide\\PhotoManager "
        f"Path PC Casa: C:\\Users\\c333053\\Dev\\photoArchiveManagerGUI-master"
    )

    with open(os.path.join(base_path, filename_glob), encoding="utf-8") as f:
        for line in f.readlines():
            match_master = re.search('^masterrepository=(.*)', line)
            if match_master:
                my_hash_glob['masterrepository'] = match_master[1]
                logger.debug(f"Parametro letto nel file di configurazione: #masterrepository# {match_master[1]}")

            match_selected = re.search('^selectedfolder=(.*)', line)
            if match_selected:
                my_hash_glob['selectedfolder'] = match_selected[1]
                logger.debug(f"Parametro letto nel file di configurazione #selectedfolder# {match_selected[1]}")

        my_hash_glob['masterrepository_bin'] = os.path.join(my_hash_glob['masterrepository'], "recycled-bin")
        my_hash_glob['masterrepository_prob'] = os.path.join(my_hash_glob['masterrepository'],
                                                             "destination_folder_problems")
        my_hash_glob['masterrepository_bak'] = os.path.join(my_hash_glob['masterrepository'], "backup")
        my_hash_glob['masterrepository_work'] = os.path.join(my_hash_glob['masterrepository'], "work-area")
        my_hash_glob['masterrepository_restore'] = os.path.join(my_hash_glob['masterrepository'], "restoredfiles")
        my_hash_glob['masterrepository_originals'] = os.path.join(my_hash_glob['masterrepository'], "foto_originali")
        my_hash_glob['masterrepository_modified'] = os.path.join(my_hash_glob['masterrepository'], "modified")
        my_hash_glob['masterrepository_unknown_changes'] = os.path.join(my_hash_glob['masterrepository'],
                                                                        "changes_unknown")

        my_hash_glob['f_copia'] = {
            'copied': [],
            'skipped': [],
            'originals': [],
            'modified': [],
            'change_unknown': [],
            'file_errors': [],
            'tot_files': [],
            'tot_dirs': [],
            'importdir_error': []
        }

        my_hash_glob['f_listaestensioni'] = {}
        my_hash_glob['f_checkarchivio'] = {
            'tot_dirs': [],
            'tot_files': [],
            'duplicatedfiles_dict': {}
        }

        my_hash_glob['f_fixdate'] = {
            'fixed': [],
            'skipped': [],
            'tot_files': [],
            'tot_dirs': [],
            'dstfolder': [],
            'filelist': [],
            'filelist_original': []
        }

        my_hash_glob['f_restore'] = {
            'tot_dirs': [],
            'original-restored': [],
            'original-duplicated': [],
            'non-original-restored': [],
            'non-original-duplicated': [],
            'tot_files': [],
            'reading_error_files': [],
            'original-copyerrors': [],
            'non-original-copyerrors': [],
            'error_files': [],
            'dstfolder': []
        }

        my_hash_glob['f_loadextension'] = {
            'root_folder': [],
            'extension_list': []
        }

        my_hash_glob['f_checkiforiginal'] = {
            'tot_dirs': [],
            'tot_files': [],
            'originals': [],
            'not_originals': []
        }

        my_hash_glob['f_crealista'] = {
            'tot_files': [],
            'tot_dirs': []
        }

        my_hash_glob['f_fotostat'] = {
            'tot_files': [],
            'filelist': [],
            'taglist_dict': {},
            'stat_tupledict': {}
        }

    return my_hash_glob


class PhotoManagerMainFrame(wx.Frame):
    def __init__(self, parent, title, *args, **kw):
        super().__init__(*args, **kw)
        wx.Panel.__init__(self, parent, title=title, size=(725, 700))
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
        self.globpropsHash = load_properties_and_init_archive(self.basePath, self.baseFile, ".masterrepository.conf")
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
        self.avviaCopiaFile = wx.Button(self, label="Avvia Import In Archivio Master", pos=(360, 140), size=(345, -1))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.modoCopia = wx.RadioBox(self, label="Azione Su File IMPORTATI/SKIPPATI:", majorDimension=3,
                                     pos=(360, 180), size=(345, -1),
                                     choices=["nessuna azione", "cestino archivio", "cestino windows"])
        self.avviaCheckArchivio = wx.Button(self, label="Avvia Controllo Duplicati Cartella Selezionata", pos=(360, 55),
                                            size=(345, -1))
        self.avviaCheckArchivio.Bind(wx.EVT_BUTTON, self.AvviaCheckArchivio)

        self.avviaFixDateTime = wx.Button(self, label="Avvia Fix Orario Cartella Selezionata", pos=(360, 410),
                                          size=(345, -1))
        self.avviaFixDateTime.Bind(wx.EVT_BUTTON, self.AvviaFixDateTime)
        self.modoFixData = wx.RadioBox(self, label="Attraversare Sotto Cartelle Sì/No", majorDimension=2,
                                       pos=(360, 440), size=(345, -1),
                                       choices=["Sì", "No"])

        self.avviaFotoStat = wx.Button(self, label="Avvia Calcola Statistiche", pos=(360, 280),
                                       size=(345, -1))
        self.avviaFotoStat.Bind(wx.EVT_BUTTON, self.AvviaFotoStat)

        self.avviaRestore = wx.Button(self, label="Avvia Restore file _original dal folder selezionato", pos=(360, 320),
                                      size=(345, -1))
        self.avviaRestore.Bind(wx.EVT_BUTTON, self.AvviaRestore)

        self.avviaCheckIfOriginal = wx.Button(self, label="Avvia CheckIfOriginal", pos=(360, 360),
                                              size=(345, -1))
        self.avviaCheckIfOriginal.Bind(wx.EVT_BUTTON, self.AvviaCheckIfOriginal)

        self.esci = wx.Button(self, label="ESCI", pos=(360, 550), size=(345, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)
        self.outputWindow = wx.TextCtrl(self, pos=(5, 280), size=(345, 300), style=wx.TE_MULTILINE)
        self.SetFocus()
        self.Center()
        self.Show(True)

    import logging
    import re


    def file_dict_show(self, function='davide', short_fmt=False):
        output_message = ''
        summary = ''
        logging.debug(f'Function to show {function}')

        if function in self.globpropsHash.keys():
            logging.debug(f'Function defined {function}')
            summary = f'Function: {function}\n'

            for p in self.globpropsHash[function]:
                match = re.search('_dict', p)

                if match:
                    logging.debug(f'Parameter {p} is a dict')
                    output_message += f'> {function} {p} distinct elements: {len(self.globpropsHash[function][p].keys())}\n'
                    summary += f'{p}-file distinct elements: {len(self.globpropsHash[function][p].keys())}'

                    for k, v in self.globpropsHash[function][p].items():
                        output_message += f'Key>> {k} >>Value {v}\n'
                        logging.debug(
                            f'Function {function} Parameter {p} Key {k} Value {self.globpropsHash[function][p][k]}')
                    output_message += '\n'
                else:
                    match = re.search('_tupledict', p)

                    if match:
                        pass
                        output_message += f'> {function} {p} distinct elements: {len(self.globpropsHash[function][p].keys())}\n'
                        summary += f'{p}-file distinct elements: {len(self.globpropsHash[function][p].keys())}'

                        for k, v in self.globpropsHash[function][p].items():
                            output_message += k
                            for l in v:
                                output_message += f', {l[0]}, {l[1]}\n'
                            logging.debug(
                                f'Function {function} Parameter {p} Key {k} Value {self.globpropsHash[function][p][k]}')
                        output_message += '\n'
                        logging.debug('Handling Tuple')
                    else:
                        n = len(self.globpropsHash[function][p])
                        output_message += f'> {function} {p} ({n})\n'
                        summary += f'{p} {n}\n'

                        for v in self.globpropsHash[function][p]:
                            output_message += f'{n} >> {v}\n'
                            logging.debug(f'Function {function} Parameter {p} Value {v}')
                            n -= 1
                        output_message += '\n'
        else:
            logging.debug(f'Function not defined {function}')
            summary = 'Unable to show output for executed function'

        if short_fmt:
            return summary

        output_message += '\n START CSV \n'
        output_message += 'File'

        for headers in self.globpropsHash['f_fotostat']['taglist_dict'].keys():
            output_message += f' , {headers}'
        output_message += '\n'

        for fp in self.globpropsHash[function]:
            match = re.search('_tupledict', fp)

            if match:
                logging.debug('Found Collection of Tuples')

                for f, d in self.globpropsHash[function]['stat_tupledict'].items():
                    logging.debug(f'File: {f} Data: {d}')
                    output_message += f

                    for key_tag in self.globpropsHash['f_fotostat']['taglist_dict'].keys():
                        for item in d:
                            if item[0] == key_tag:
                                output_message += f' , {item[1]}'

                    output_message += '\n'

        output_message += '\n END CSV \n'
        return output_message + summary

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
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_loadextension', True), style=wx.ICON_INFORMATION,
                                   caption="Esecuzione Lista Estensioni Terminata")
        okCheck.ShowModal()
        self.outputWindow.SetValue(self.file_dict_show('f_loadextension'))
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
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_restore', True), style=wx.ICON_INFORMATION,
                                   caption="Restore Terminata")
        okCheck.ShowModal()
        self.outputWindow.SetValue(self.file_dict_show('f_restore'))
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
                                    logger.info('File %s restorato su %s', file.path, dstfile)
                                else:
                                    self.globpropsHash['f_restore']['original-duplicated'].append(file.path)
                                    logger.info('File %s duplicato inutile restorarea su %s', file.path, dstfile)
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

    def creaListaFile(self, dir='c:\\temp\\', walkDir=True, function='f_fixdate'):
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_crealista']['tot_dirs']))
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    logger.debug('DirEntry %s è una directory: %s', id_log_counter_dir, file.path)
                    if walkDir == False:
                        logger.debug("DIRECTORY %s <NON ATTRAVERSO LA DIRECTORY> %s", id_log_counter_dir,
                                     file.path)
                    else:
                        logger.debug("DIRECTORY %s <ATTRAVERSO LA DIRECTORY> %s", id_log_counter_dir, file.path)
                        self.globpropsHash['f_crealista']['tot_dirs'].append(file.path)
                        self.creaListaFile(file.path, True, function)
                        logger.debug("DIRECTORY %s_ %s Aggiunta", id_log_counter_dir, file.path)

                else:
                    id_log_counter = str(len(self.globpropsHash['f_crealista']['tot_files']))
                    logger.debug("FILE %s_%s Trovato:  %s", id_log_counter_dir, id_log_counter, file.path)
                    match = re.search('_original', pathlib.Path(file).suffix)
                    if match:
                        logger.debug('File %s da saltare, ha estensione: %s', file.path, str(match[0]))
                        # self.globpropsHash[function]['filelist_original'].append(file.path)
                    else:
                        self.globpropsHash[function]['filelist'].append(file.path)
                        logger.info("FILE %s_%s <-> %s Aggiunto", id_log_counter_dir, id_log_counter, file.path)

    def AvviaFixDateTime(self, evt):
        self.CleanConfigFunction()
        self.globpropsHash['f_fixdate']['dstfolder'] = [self.fileTS()]
        self.FixDateTime(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.file_dict_show('f_fixdate'))
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_fixdate', True), style=wx.ICON_INFORMATION,
                                   caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def FixDateTime(self, dir="C:\\Users\\c333053\\TestImport"):
        self.fixmode = self.modoFixData.GetSelection()
        if self.fixmode == 0:
            self.creaListaFile(self.globpropsHash['selectedfolder'], True, 'f_fixdate')
        else:
            self.creaListaFile(self.globpropsHash['selectedfolder'], False, 'f_fixdate')
        if os.path.exists(dir):
            id_log_counter_dir = str(len(self.globpropsHash['f_fixdate']['tot_dirs']))
            logger.info("<<<INIZIO CARTELLA %s >>>", dir)
            self.globpropsHash['f_fixdate']['tot_dirs'].append(dir)

            for file in self.globpropsHash['f_fixdate']['filelist']:
                if os.path.isdir(file):
                    logger.error('Trovato un file nella lista che invece è una directory %s', file)
                else:
                    id_log_counter = str(len(self.globpropsHash['f_fixdate']['tot_files']))
                    logger.debug("FILE %s_%s <INIZIO> %s", id_log_counter_dir, id_log_counter, file)
                    with exiftool.ExifTool() as et:
                        # Al momento fisso a +7 ore
                        deltaDateTime = '00:00:00 07:00:00'
                        exiftoolModDatePar = '-ModifyDate+=\"' + deltaDateTime + '\"'
                        exiftoolCreateDatePar = '-CreateDate+=\"' + deltaDateTime + '\"'
                        exiftoolOrigDatePar = '-DateTimeOriginal+=\"' + deltaDateTime + '\"'
                        logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ", id_log_counter_dir,
                                     id_log_counter, exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar)
                        try:
                            et.execute(exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar, file)
                            logger.debug("FILE %s_%s <EXIFTOOL PARAMETRI: %s, %s, %s, > ", id_log_counter_dir,
                                         id_log_counter, exiftoolModDatePar, exiftoolCreateDatePar, exiftoolOrigDatePar)
                            logger.debug("FILE %s_%s <STDOUT CMD EXIFTOOL %s > ", id_log_counter_dir, id_log_counter,
                                         str(et.last_stdout).replace('\n', ''))
                            logger.debug("FILE %s_%s <STDERR CMD EXIFTOOL %s > ", id_log_counter_dir, id_log_counter,
                                         str(et.last_stderr))
                            logger.debug("FILE %s_%s <RISULTATO CMD EXIFTOOL %s", id_log_counter_dir, id_log_counter,
                                         str(et.last_status))
                            if et.last_status == 0 and et.last_stdout.rfind('unchanged') < 0:
                                self.globpropsHash['f_fixdate']['fixed'].append(file)
                                srcmvfullfilename = file + '_original'
                                logger.debug('File sorgente da spostare: %s', srcmvfullfilename)
                                if os.path.exists(srcmvfullfilename):
                                    dstbckfilename = pathlib.Path(srcmvfullfilename).name
                                    logger.debug('Nome file destinazione spostamento: %s', dstbckfilename)
                                    dstbckfoldername = self.globpropsHash['masterrepository_bak'] + '\\' + \
                                                       self.globpropsHash['f_fixdate']['dstfolder'][0]
                                    logger.debug('Nome Cartella destinazione spostamento: %s', dstbckfoldername)
                                    dstbckfullfilename = dstbckfoldername + '\\' + dstbckfilename
                                    logger.debug('Nome Completo file destinazione spostamento: %s', dstbckfullfilename)
                                    if not os.path.exists(dstbckfoldername):
                                        os.makedirs(dstbckfoldername)
                                    try:
                                        if not os.path.exists(dstbckfullfilename):
                                            shutil.move(srcmvfullfilename, dstbckfullfilename, copy_function='copy2')
                                            logger.info('File backup di Exiftool Spostato da qui: %s a qui: %s',
                                                        srcmvfullfilename, dstbckfullfilename)
                                        else:
                                            n = 1
                                            while n > 0:
                                                if not os.path.exists(dstbckfullfilename + '_' + str(n)):
                                                    shutil.move(srcmvfullfilename, dstbckfullfilename + '_' + str(n),
                                                                copy_function='copy2')
                                                    logger.info('File backup di Exiftool Spostato da qui: %s a qui: %s',
                                                                srcmvfullfilename, dstbckfullfilename + '_' + str(n))
                                                    n = -1
                                                else:
                                                    n += 1
                                    except Exception as ex:
                                        logger.error(
                                            'Errore spostamento file da qui: %s a qui: %s con questa motivazione: %s',
                                            srcmvfullfilename, dstbckfullfilename, str(ex))
                                logger.info("FILE %s_%s <Data-Ora Aggiornata> %s", id_log_counter_dir, id_log_counter,
                                            file)
                            else:
                                logger.error("<<PROBLEMA ESECUZIONE EXIF su file: %s ", file)
                                self.globpropsHash['f_fixdate']['skipped'].append(file)
                        except Exception as e:
                            logger.error("<<ERRORE SUL FILE: %s ERRORE: %s ", file, str(e))
                        self.globpropsHash['f_fixdate']['tot_files'].append(file)
            logger.info("<<<FINE CARTELLA>>> <<< %s >>>", dir)

    def convertvalue(self, inputvalue='', operation='none'):
        if operation == 'fraction_to_decimal':
            logger.debug('Risultato split: %s', inputvalue.split(sep='/'))
            try:
                num, den = inputvalue.split(sep='/')
            except ValueError as ver:
                logger.error('Valore di input non è una frazione valida: %s motivo: %s', inputvalue, str(ver))
                return float(inputvalue)
            logger.debug('Numeratore: %s', num)
            logger.debug('Denominatore: %s', den)
            try:
                logger.debug('Sto per restituire il numero: float(float(num)/float(den)) %s',
                             str(float(float(num) / float(den))))
                return float(float(num) / float(den))
            except ValueError as ver:
                logger.error('Valore di input non valido: %s motivo: %s', inputvalue, str(ver))
        return inputvalue

        return output

    def AvviaFotoStat(self, evt):
        self.CleanConfigFunction()

        self.globpropsHash['f_fotostat']['taglist_dict']['Image Model'] = ['none']
        self.globpropsHash['f_fotostat']['taglist_dict']['Image DateTime'] = ['none']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF DateTimeOriginal'] = ['none']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF ExposureTime'] = ['none']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF FNumber'] = ['fraction_to_decimal']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF ExposureProgram'] = ['none']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF FocalLength'] = ['fraction_to_decimal']
        self.globpropsHash['f_fotostat']['taglist_dict']['EXIF FocalLengthIn35mmFilm'] = ['none']

        self.FotoStat(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.file_dict_show('f_fotostat'))
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_fotostat', True), style=wx.ICON_INFORMATION,
                                   caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def FotoStat(self, dir="C:\\Users\\c333053\\TestImport"):
        self.creaListaFile(self.globpropsHash['selectedfolder'], True, 'f_fotostat')
        if os.path.exists(dir):
            for file in self.globpropsHash['f_fotostat']['filelist']:
                if os.path.isdir(file):
                    logger.error('Trovato un file nella lista che invece è una directory %s', file)
                else:
                    id_log_counter_file = str(len(self.globpropsHash['f_fotostat']['tot_files']))
                    logger.debug("FILE %s <INIZIO> %s", id_log_counter_file, file)
                    try:
                        with open(pathlib.Path(file), 'rb') as image_exif:
                            if image_exif:
                                logger.debug("FILE %s <ha exif tags> %s ",
                                             str(id_log_counter_file), file)
                                exif_tags = exifread.process_file(image_exif)

                                # RIPRENDI
                                if file not in self.globpropsHash['f_fotostat']['stat_tupledict'].keys():
                                    self.globpropsHash['f_fotostat']['stat_tupledict'][file] = []

                                for chiave, valore in exif_tags.items():
                                    # logger.debug('<EXIF TAGS> Chiave: %s --> Valore: %s',chiave,valore)
                                    if chiave in self.globpropsHash['f_fotostat']['taglist_dict'].keys():
                                        logger.debug('Elemento lista TAG interessanti Trovato: %s, valore: %s', chiave,
                                                     valore)
                                        try:
                                            operation = self.globpropsHash['f_fotostat']['taglist_dict'][chiave][0]
                                            value = str(valore)
                                            converted_value = self.convertvalue(value, operation)
                                            tupla = (chiave, converted_value)
                                            logger.debug('Cerco di trovare la tupla...tupla[0]= %s tupla[1]= %s',
                                                         tupla[0], tupla[1])
                                            self.globpropsHash['f_fotostat']['stat_tupledict'][file].append(tupla)
                                            logger.info('File %s <Aggiungo tupla [%s , %s] >', file, chiave, valore)
                                        except ValueError as ver:
                                            logger.error('Valori in EXIF DATA non corretto nel file %s errore: %s',
                                                         file, str(ver))
                    except UnidentifiedImageError as ime:
                        logger.error("Immagine Non identificata %s errore: %s", file.path, str(ime))

    def AvviaCheckArchivio(self, evt):
        self.CleanConfigFunction()
        self.CheckArchivio(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.file_dict_show('f_checkarchivio'))
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_checkarchivio', True), style=wx.ICON_INFORMATION,
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
        self.outputWindow.SetValue(self.file_dict_show('f_copia'))
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_copia', True), style=wx.ICON_INFORMATION,
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

                        dstroot = self.globpropsHash['masterrepository_unknown_changes']
                        logger.debug('Destinazione copia impostata su %s', dstroot)

                        dstcamerafolder = "ProduttoreNonNoto\\ModelloNonNoto"
                        dstmaker = 'ProduttoreNonNoto'
                        dstmodel = 'ModelloNonNoto'
                        dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                        dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                        dstdayfolder = time.strftime("%d", time.gmtime(os.path.getmtime(file)))
                        logger.debug('Cartella Giorno: day: %s', dstdayfolder)
                        dstext = os.path.splitext(file)[1].lower()
                        try:
                            with open(pathlib.Path(file), 'rb') as image_exif:
                                if image_exif:
                                    logger.debug("FILE %s_%s <ha exif tags> %s ", str(id_log_counter_dir),
                                                 str(id_log_counter_file), file.path)
                                    exif_tags = exifread.process_file(image_exif)
                                    originaldatetimetag = 'EXIF DateTimeOriginal'
                                    originaldatetimevalue = ''
                                    imagedatetimetag = 'Image DateTime'
                                    imagedatetimevalue = ''
                                    makertag = 'Image Make'
                                    makervalue = ''
                                    modeltag = 'Image Model'
                                    modelvalue = ''
                                    if originaldatetimetag in exif_tags.keys():
                                        originaldatetimevalue = str(exif_tags[originaldatetimetag])
                                        try:
                                            logger.debug("FILE %s_%s <Anno/Mese da DataFile <MODIFICA FILE>:> %s / %s ",
                                                         str(id_log_counter_dir), str(id_log_counter_file),
                                                         dstyearfolder, dstmonthfolder)
                                            dstyearfolder = time.strftime("%Y",
                                                                          time.strptime(originaldatetimevalue,
                                                                                        "%Y:%m:%d %H:%M:%S"))
                                            dstmonthfolder = time.strftime("%m",
                                                                           time.strptime(originaldatetimevalue,
                                                                                         "%Y:%m:%d %H:%M:%S"))
                                            dstdayfolder = time.strftime("%d",
                                                                         time.strptime(originaldatetimevalue,
                                                                                       "%Y:%m:%d %H:%M:%S"))
                                            logger.debug(
                                                "FILE %s_%s <Anno/Mese da DataFile <DATETIME ORIGINAL>:> %s / %s ",
                                                str(id_log_counter_dir), str(id_log_counter_file),
                                                dstyearfolder, dstmonthfolder)

                                            # ESISTE ORIGINALE--> se modificata va in modified se no original
                                            if imagedatetimetag in exif_tags.keys():
                                                imagedatetimevalue = str(exif_tags[imagedatetimetag])
                                                if imagedatetimevalue == originaldatetimevalue:
                                                    self.globpropsHash['f_copia']['originals'].append(file.path)
                                                    logger.debug('File %s ORIGINALE', file.path)
                                                    dstroot = self.globpropsHash['masterrepository_originals']

                                                else:
                                                    logger.debug('File %s MODIFIED', file.path)
                                                    self.globpropsHash['f_copia']['modified'].append(file.path)
                                                    dstroot = self.globpropsHash['masterrepository_modified']
                                            else:
                                                dstroot = self.globpropsHash['masterrepository_originals']
                                                logger.debug(
                                                    "FILE %s_%s <Anno/Mese da DataFile <DATETIME ORIGINAL SENZA IMAGEMODIFY>:> %s / %s ",
                                                    str(id_log_counter_dir), str(id_log_counter_file),
                                                    dstyearfolder, dstmonthfolder)
                                                self.globpropsHash['f_copia']['originals'].append(file.path)
                                        except ValueError as ver:
                                            logger.error('Valori in EXIF DATE non corretti nel file %s errore: %s',
                                                         file.path,
                                                         str(ver))
                                            dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                                            dstmonthfolder = time.strftime("%m", time.gmtime(os.path.getmtime(file)))
                                            dstdayfolder = time.strftime("%d", time.gmtime(os.path.getmtime(file)))
                                            logger.error(
                                                'Valori di data destinazione ripristinati da nome file per il file  %s.',
                                                file.path)
                                            self.globpropsHash['f_copia']['change_unknown'].append(file.path)
                                            logger.debug('File %s UNKNOWN CHANGE, but OriginalTAGS are present',
                                                         file.path)
                                    else:
                                        if imagedatetimetag in exif_tags.keys():
                                            imagedatetimevalue = str(exif_tags[imagedatetimetag])
                                            try:

                                                logger.debug("FILE %s_%s <Anno/Mese da DataFile:> %s / %s ",
                                                             str(id_log_counter_dir), str(id_log_counter_file),
                                                             dstyearfolder, dstmonthfolder)
                                                dstyearfolder = time.strftime("%Y",
                                                                              time.strptime(imagedatetimevalue,
                                                                                            "%Y:%m:%d %H:%M:%S"))
                                                dstmonthfolder = time.strftime("%m",
                                                                               time.strptime(imagedatetimevalue,
                                                                                             "%Y:%m:%d %H:%M:%S"))
                                                dstdayfolder = time.strftime("%d",
                                                                             time.strptime(imagedatetimevalue,
                                                                                           "%Y:%m:%d %H:%M:%S"))
                                                logger.debug("FILE %s_%s <Anno/Mese da DataFile:> %s / %s ",
                                                             str(id_log_counter_dir), str(id_log_counter_file),
                                                             dstyearfolder, dstmonthfolder)
                                                self.globpropsHash['f_copia']['modified'].append(file.path)

                                            except ValueError as ver:
                                                logger.error('Valori in EXIF DATE non corretti nel file %s errore: %s',
                                                             file.path,
                                                             str(ver))
                                                dstyearfolder = time.strftime("%Y", time.gmtime(os.path.getmtime(file)))
                                                dstmonthfolder = time.strftime("%m",
                                                                               time.gmtime(os.path.getmtime(file)))
                                                dstdayfolder = time.strftime("%d", time.gmtime(os.path.getmtime(file)))
                                                logger.error(
                                                    'Valori di data destinazione ripristinati da nome file per il file  %s.',
                                                    file.path)
                                                self.globpropsHash['f_copia']['change_unknown'].append(file.path)
                                                logger.debug('File %s UNKNOWN CHANGE, but Modified TAGS  are present',
                                                             file.path)
                                    # SE SONO QUI NON SO SE ORIGINALE O NO
                                    if makertag in exif_tags.keys():
                                        try:
                                            makervalue = str(exif_tags[makertag])
                                            dstmaker = makervalue.strip().replace(' ', '')
                                            dstcamerafolder = dstmaker
                                            logger.debug("FILE %s_%s <PRODUTTORE:> %s", str(id_log_counter_dir),
                                                         str(id_log_counter_file), dstmaker)
                                        except ValueError as verMaker:
                                            dstmaker = 'ProduttoreNonNoto'
                                            logger.error(
                                                'Produttore reimpostato su non noto  per il file %s.',
                                                file.path)
                                    if modeltag in exif_tags.keys():
                                        try:
                                            modelvalue = str(exif_tags[modeltag])
                                            dstmodel = modelvalue.strip().replace(' ', '-')
                                            logger.debug("FILE %s_%s <MODELLO:> %s", str(id_log_counter_dir),
                                                         str(id_log_counter_file), dstmodel)
                                        except:
                                            dstmodel = 'ModelloNonNoto'
                                            logger.error(
                                                'Modello  reimpostato su non noto  per il file %s.',
                                                file.path)
                                    dstcamerafolder = dstmaker + "\\" + dstmodel
                                    logger.debug("FILE %s_%s <FOTOCAMERA:> %s", str(id_log_counter_dir),
                                                 str(id_log_counter_file), dstcamerafolder)
                        except UnidentifiedImageError as ime:
                            logger.error("Immagine Non identificata %s errore: %s", file.path, str(ime))
                        if dstroot == self.globpropsHash['masterrepository_unknown_changes']:
                            self.globpropsHash['f_copia']['change_unknown'].append(file.path)
                        dstfolder = dstroot + "\\" + dstcamerafolder + "\\" + dstyearfolder + "\\" + dstmonthfolder + "\\" + dstdayfolder
                        dstfile = dstfolder + "\\" + md5filename + dstext
                        logger.debug("FILE %s_%s <Destinazione individuata:> %s", str(id_log_counter_dir),
                                     str(id_log_counter_file), dstfile)
                        logger.debug("FILE %s_%s <CopyMode:> %s", str(id_log_counter_dir), str(id_log_counter_file),
                                     dstroot)
                        if not os.path.exists(self.globpropsHash['masterrepository_bin']):
                            os.makedirs(self.globpropsHash['masterrepository_bin'])
                            logger.debug("FOLDER_CESTINO_ARCHIVIO: %s", self.globpropsHash['masterrepository_bin'])
                        [dstdrive, dstfile_nodrive] = os.path.splitdrive(dstfile)
                        try:
                            validate_filepath(dstfile_nodrive)
                        except ValidationError as ev:
                            logger.error(
                                "FILE %s_%s <La Destinazione individuata per il file:> %s ha un problema, lo sposto negli scarti",
                                str(id_log_counter_dir),
                                str(id_log_counter_file), file.path)
                            dstfolder = self.globpropsHash['masterrepository_prob']
                            dstfile = dstfolder + "\\" + md5filename + dstext
                            logger.error("******** DESTINAZIONE AGGIORNATA: ")
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
                        logger.error('Errore nell \'apertura del file %s errore: %s eccezione:', file.path, str(er))
                        pass
            logger.info("FILE %s <Chiusura Cartella> %s", id_log_counter_dir, dir)
            dir_iterator.close()
        else:
            dlg = wx.MessageDialog(self, "Directory Import Inesistente", style=wx.ICON_ERROR,
                                   caption="Directory Import Inesistente")
            dlg.ShowModal()

    def AvviaCheckIfOriginal(self, evt):
        self.CleanConfigFunction()
        self.CheckIfOriginal(self.globpropsHash['selectedfolder'])
        self.gauge.SetValue(self.gauge.GetRange())
        self.outputWindow.SetValue(self.file_dict_show('f_checkiforiginal'))
        okCheck = wx.MessageDialog(self, self.file_dict_show('f_checkiforiginal', True), style=wx.ICON_INFORMATION,
                                   caption="Check Terminato")
        okCheck.ShowModal()
        self.gauge.SetValue(0)
        self.CleanConfigFunction()

    def CheckIfOriginal(self, dir="C:\\Users\\c333053\\TestImport"):
        self.globpropsHash['f_checkiforiginal']['tot_dirs'].append(dir)
        id_log_counter_dir = len(self.globpropsHash['f_checkiforiginal']['tot_dirs'])

        if os.path.exists(dir):
            dir_iterator = os.scandir(dir)
            for file in dir_iterator:
                if file.is_dir():
                    logger.debug("FILE %s_ <è una directory> %s", id_log_counter_dir, str(file.path))
                    self.CheckIfOriginal(str(file.path))
                else:
                    id_log_counter_file = len(self.globpropsHash['f_checkiforiginal']['tot_files'])
                    self.gauge.SetValue(len(self.globpropsHash['f_checkiforiginal']['tot_files']))
                    logger.debug("FILE %s_%s  <APERTURA FILE> %s", id_log_counter_dir, id_log_counter_file,
                                 str(file.path))
                    try:
                        with open(file, "rb") as fmd5:
                            md5filename = hashlib.file_digest(fmd5, "md5").hexdigest()

                            logger.debug("FILE %s_%s <md5 calcolato> %s", id_log_counter_dir, id_log_counter_file,
                                         md5filename)
                            ext = pathlib.Path(file).suffix
                            logger.debug("FILE %s_%s <extension calcolato> %s", id_log_counter_dir, id_log_counter_file,
                                         ext)
                            if file.name == (md5filename + ext):
                                self.globpropsHash['f_checkiforiginal']['originals'].append(file.path)
                                logger.debug('FILE %s_%s <Inserito nuovo file nella lista originals:> %s',
                                             id_log_counter_dir, id_log_counter_file, file.path)
                                logger.info('FILE %s_%s <Inserito nuovo file nella lista originals:> %s',
                                            id_log_counter_dir, id_log_counter_file, file.path)
                            else:
                                self.globpropsHash['f_checkiforiginal']['not_originals'].append(file.path)
                                logger.debug('FILE %s_%s <Inserito nuovo file nella lista NOT-originals:> %s',
                                             id_log_counter_dir, id_log_counter_file, file.path)
                                logger.info('FILE %s_%s <Inserito nuovo file nella lista NOT-originals:> %s',
                                            id_log_counter_dir, id_log_counter_file, file.path)
                            fmd5.close()
                            self.globpropsHash['f_checkiforiginal']['tot_files'].append(file.path)
                    except IOError as eio:
                        logger.error('ERRORE FILE errore %s', str(eio))
                    logger.debug("FILE %s_%s <CHIUSURA FILE> %s", id_log_counter_dir, id_log_counter_file,
                                 str(file.path))
                    self.gauge.SetValue(len(self.globpropsHash['f_checkarchivio']['tot_files']))
            dir_iterator.close()
            logger.debug("<<< %s >>> %s <<<FINE CARTELLA>>>", str(dir), id_log_counter_dir)



def configure_logger():
    # Configure file logger
    file_handler = logging.FileHandler('photoark.log', mode='w')  # Change 'photoark.log' to your desired log file name
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(lineno)s-%(funcName)s()] %(message)s")
    file_handler.setFormatter(file_formatter)

    # Configure stream (console) logger
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(lineno)s-%(funcName)s()] %(message)s")
    stream_handler.setFormatter(stream_formatter)

    # Create logger and add handlers
    logger = logging.getLogger('photoark')
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Set logging levels
    logger.setLevel(logging.DEBUG)  # Set the overall logging level to DEBUG
    stream_handler.setLevel(logging.INFO)  # Set console logging level to INFO

    logger.propagate = False
    logger.debug('Logger initialization complete')
    return logger

if __name__ == '__main__':
    logger = configure_logger()

    app = wx.App()
    main_frame = PhotoManagerMainFrame(None, "PhotoManager")
    app.MainLoop()