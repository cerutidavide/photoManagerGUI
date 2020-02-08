import logging
import magic
import os
import re
import shutil
import stat
import subprocess
import time
import unittest
import wx


#TODO preparare stringa comandi per md5
# input_string='/Users/us01621/Music/Giuliano Palma & The Bluebeaters - The Album/07 . Wonderful Life.mp3'
# output_string=input_string.replace('&','\&').replace(' ','\ ')
# commandstring='md5 '+output_string
# subprocess.run(commandstring,shell=True)
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#TODO barra di avanzamento su cerca duplicati
#TODO dato un file (o una lista di file) trovare se c'è nell'archivio un file identico oppure no





def loadFileExtensionList(filepath="/tmp/", extensionList=[], firstcall=True):
    logging.debug("Folder in elaborazione: " + filepath)
    if firstcall is True:
        extensionList = []
    try:
        for file in os.listdir(filepath):
            logging.debug('File corrente: '+filepath+'/'+file)
            if os.path.isdir(filepath + "/" + file):
                loadFileExtensionList(filepath + "/" + file, extensionList, False)
                pass
            else:
                ext = os.path.splitext(filepath + "/" + file)
                if ext[1] != "":
                    if ext[1] not in extensionList:
                        extensionList.append(ext[1])
                        logging.debug('Trovata nuova estensione: ' + ext[1])
    except:
        logging.error('Errore accedendo al folder: '+filepath+'/'+file)
    return extensionList
    pass


def logDuplicati(duplicatedListDict={}):
    for key in duplicatedListDict.keys():
        if len(duplicatedListDict[key])>1:
            logging.info(key+'------------->>>>>'+str(duplicatedListDict[key]))
    pass


def CheckAndLoadProperties(workingdir='/Users/us01621/SviluppoDavide/PycharmProjects/photoManagerGUI',
                           filenameGlob="default.props", filenameMstr=".masterrepository.conf"):
    myHashGlob = {}
    myHashGlob['fileconfprincipale'] = filenameGlob
    logging.debug("fileconfprincipale: " + filenameGlob)
    myHashGlob['masterrepositoryconf'] = filenameMstr
    with open(os.path.join(workingdir, filenameGlob), encoding="utf-8") as f:
        for line in f.readlines():
            # print(line)
            match = re.search('^masterrepository=(.*)', line)
            # print(match)
            if match:
                myHashGlob['masterrepository'] = match[1]
            match = re.search('^importfolder=(.*)', line)
            if match:
                myHashGlob['importfolder'] = match[1]
            match = re.search('^importfilelist=(.*)', line)
            if match:
                myHashGlob['importfilelist'] = match[1]
    logging.debug(myHashGlob)
    with open(myHashGlob['masterrepository'] + filenameMstr, encoding="utf-8") as f:
        for line in f.readlines():
            match = re.search('^masterrepositoryfilelist=(.*)', line)
            if match:
                myHashGlob['masterrepositoryfilelist'] = match[1]
            match = re.search('^masterrepositoryisready=(.*)', line)
            if match:
                myHashGlob['masterrepositoryisready'] = match[1]
            match = re.search('^masterrepositorysize=(.*)', line)
            if match:
                myHashGlob['masterrepositorysize'] = match[1]
    logging.debug("Dopo caricamento repository: " + str(myHashGlob))
    return myHashGlob


# INTERFACCIA GRAFICA APPLICAZIONE


def printDuplicated(duplicatedfileHash={}):

    for key in duplicatedfileHash:
        print(duplicatedfileHash[key])
        # if len(duplicatedfileHash[key])>1:
        #     print('chiave '+key+'valore '+str(duplicatedfileHash[key]))
        # else:
        #     print('file singolo: '+key)
    pass
def calcNumberOfFile(filepath='/tmp/',numfile={},firstcall=True):
    if firstcall is True:
        logging.debug("Calcolo numero file per il percorso: " + filepath)
        numfile['files']=0
    for file in os.listdir(filepath):
        logging.debug('Numero file: ' + str(numfile))
        if os.path.isdir(filepath + "/" + file):
            calcNumberOfFile(filepath + "/" + file, numfile, False)
        else:
            numfile['files'] = numfile['files'] + 1
    return numfile



class PhotoManagerAppFrame(wx.Frame):
    def __init__(self, parent, title):
        logging.basicConfig(filename='/Users/us01621/PhotoArchive.log', level=logging.INFO)
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        self.checkRunning = True
        self.globpropsHash = CheckAndLoadProperties()
        logging.debug(str(self.globpropsHash))
        self.duplicatedFileHash={}
        self.importDirFileExtensions = {}
        self.importfileHash = {}
        self.importMd5fileHash = {}
        self.mstrfileHash = {}  # hash di servizio per il caricamento del file parziale
        self.copyfileHash = {}
        self.skippedfileHash = {}
        self.loggingDict = {}
        self.contatoreDebug = 0
        self.duplicatedFileDict={}
        self.labelDirList = wx.StaticText(self, label="Browse Folder:", pos=(5, 5))
        self.importDirList = wx.GenericDirCtrl(self, pos=(5, 25), size=(345, 200), style=wx.DIRCTRL_DIR_ONLY)
        self.importDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.SelezionaImportFolder)




        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file presenti nel folder selezionato ",pos=(5, 230),size=(345, -1))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)



        self.statFolder = wx.Button(self, label="Mostra statistiche file immagini folder selezionato", pos=(5, 255), size=(345, -1))
        self.statFolder.Bind(wx.EVT_BUTTON, self.avviaStatFolder)




        self.cercaDuplicati = wx.Button(self, label="Cerca file duplicati nel folder selezionato", pos=(5, 300),size=(345, -1))
        self.cercaDuplicati.Bind(wx.EVT_BUTTON, self.avviaCercaDuplicati)

        self.esci = wx.Button(self, label="ESCI", pos=(5, 450), size=(350, -1))
        self.esci.Bind(wx.EVT_BUTTON, self.Esci)


        self.gauge = wx.Gauge(self, pos=(5, 560), size=(690, -1))
        self.gauge.SetValue(0)


        numOfFile=calcNumberOfFile('/Users/us01621/ArchivioFoto/', {}, True)
        self.gauge.SetRange(numOfFile['files'])

        #self.gauge.SetRange(calcNumberOfFile(self.importDirList.GetPath(),0,True))





#        self.avviaCopiaFile = wx.Button(self, label="Avvia Copia File nel Master", pos=(5, 325))
#        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),
                                          pos=(355, 25))
        #self.loggedCopied = wx.TextCtrl(self, pos=(355, 225))
        self.SetFocus()
        self.Center()
        self.Show(True)
        self.importDirList.SetPath('/Users/us01621/ArchivioFoto/')

    def folderStats(self,filepath="/Users/us01621/ArchivioFoto/", statresults={}, firstcall=True):
        if firstcall is True:
            logging.debug("Mostro statistiche per il percorso: " + filepath)
            statresults['files'] = 0
            statresults['dirs'] = 0
            statresults['imgJPEG'] = 0
            statresults['imgPNG'] = 0
            statresults['imgRAW'] = 0
            statresults['noIMG'] = 0
            self.gauge.SetValue(0)
        for file in os.listdir(filepath):
            if os.path.isdir(filepath + "/" + file):
                logging.debug("<dir>: " + file)
                statresults['dirs'] = statresults['dirs'] + 1
                self.folderStats(filepath + "/" + file, statresults, False)
            else:
                self.gauge.SetValue(self.gauge.GetValue()+1)
                self.gauge.Refresh()
                PhotoManagerApp.Yield()
                statresults['files'] = statresults['files'] + 1
                string = ''
                try:
                    string = magic.from_file(filepath + "/" + file)
                    logging.debug('FILE:' + filepath + '/' + file + ' è di tipo: ' + string)
                except:
                    logging.error("Il tipo del file " + filepath + "/" + file + " non è riconosciuto")
                    pass
                match = re.search('^JPEG image data(.*)', string)
                if match is not None:
                    statresults['imgJPEG'] = statresults['imgJPEG'] + 1
                else:
                    match = re.search('(.*)raw image data(.*)', string)
                    if match is not None:
                        statresults['imgRAW'] = statresults['imgRAW'] + 1
                    else:
                        match = re.search('^PNG image data(.*)', string)
                        if match is not None:
                            statresults['imgPNG'] = statresults['imgPNG'] + 1
                        else:
                            statresults['noIMG'] = statresults['noIMG'] + 1
                            logging.info('File non riconosciuto come immagine: ' + filepath + "/" + file)
                            pass
        return statresults
    def cercaDuplicati_f(self,filepath="/tmp/", duplicatedListDict={}, firstcall=True):
        logging.debug("Folder in elaborazione: " + filepath)
        if firstcall is True:
            duplicatedListDict = {}
            global duplicatenumber
            global totalfilenumber
            global differentfilenumber
            duplicatenumber=0
            self.gauge.SetValue(0)
        for file in os.listdir(filepath):
            logging.debug('File corrente: ' + filepath + '/' + file)
            if os.path.isdir(filepath + "/" + file):
                self.cercaDuplicati_f(filepath + "/" + file, duplicatedListDict, False)
                pass
            else:
                try:
                    inputcommandstring=filepath + "/" + file
                    logging.debug('INPUT: '+inputcommandstring)
                    commandstring=inputcommandstring.replace(' ','\ ').replace('&','\&').replace('\'','\\\'').replace('(','\(').replace(')','\)').replace('=','\=').replace(';','\;').replace(':','\:')
                    logging.debug(commandstring)
                    p = subprocess.run('md5 '+commandstring, shell=True,
                                       universal_newlines=True,
                                       stdout=subprocess.PIPE)

                except:
                    logging.error("ERRORE eseguendo md5 sul file: "+filepath+"/"+file)
                logging.debug('Output MD5: ' + p.stdout.rstrip())
                match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                if match:
                    logging.debug('Catturata chiave: ' + match[2])
                    logging.debug('Catturato valore: ' + match[1])
                    if match[2] not in duplicatedListDict.keys():
                        duplicatedListDict[match[2]] = [match[1]]
                        logging.debug('Aggiunta chiave: ' + match[2] + 'con valore ' + match[1])
                        pass
                    else:
                        duplicatedListDict[match[2]].append(match[1])
                        duplicatenumber = duplicatenumber + 1
                        logging.debug('Aggiunto valore NUOVO ' + match[1] + ' alla chiave ' + match[2])
                        pass
                    differentfilenumber=len(duplicatedListDict)
                    totalfilenumber=differentfilenumber+duplicatenumber
                    self.gauge.SetValue(self.gauge.GetValue() + 1)
                    self.gauge.Refresh()
                    PhotoManagerApp.Yield()
                    logging.info('Adesso la mappa contiene  ' + str(differentfilenumber) + ' file diversi e ' + str(totalfilenumber) + ' in totale')
                    logging.debug('Adesso la mappa contiene  ' + str(differentfilenumber) + ' file diversi e ' + str(totalfilenumber) + ' in totale'+ 'Gauge Value: '+str(self.gauge.GetValue())+' Gauge Range: '+str(self.gauge.GetRange()))

        return duplicatedListDict

    def stringFormattedHash(self):
        result = ""
        # print("TRACE5")
        # print(self.globpropsHash.keys())
        for k in self.globpropsHash.keys():
            # print(k)
            # print(self.globpropsHash[k])
            # result=result+self.globpropsHash[k]
            result = result + k + " = " + str(self.globpropsHash[k]) + "\n"
        return result

    # ACTIONS
    def avviaStatFolder(self,evt):
        logging.debug('Folder selezionato: '+self.importDirList.GetPath())
        self.gauge.SetRange(calcNumberOfFile(self.importDirList.GetPath(),{},firstcall=True)['files'])
        statdict=self.folderStats(self.importDirList.GetPath(),{},True)
        self.messageExtension = wx.MessageBox("Di seguito le statistiche del folder selezionato: \n" + str(statdict), '', wx.CLOSE)
        self.gauge.SetValue(0)

    def avviaCercaDuplicati(self,evt):
        logging.debug('Folder selezionato: ' + self.importDirList.GetPath())
        self.gauge.SetRange(calcNumberOfFile(self.importDirList.GetPath(),{},firstcall=True)['files'])
        self.duplicatedFileHash = self.cercaDuplicati_f(self.importDirList.GetPath(),{},True)
        logDuplicati(self.duplicatedFileHash)
        self.messageExtension = wx.MessageBox('Numero di file univoci trovati: '+ str(len(self.duplicatedFileHash))+'\nNumero di duplicati: '+str(duplicatenumber), '', wx.CLOSE)
        self.gauge.SetValue(0)



    def SelezionaImportFolder(self, evt):
        self.globpropsHash['importfolder'] = self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())


    def AvviaCaricaEstensioni(self, evt):
        # self.importDirFileExtensions = loadFileExtensionList(self.globpropsHash['importfolder'])
        self.SelezionaImportFolder(evt)
        logging.debug(self.globpropsHash['importfolder'])


        self.messageExtension = wx.MessageBox("Nel folder import ci sono i seguenti tipi di file: \n" + str(
            loadFileExtensionList(self.globpropsHash['importfolder'], True)), '', wx.CLOSE)

        # print(loadFileExtensionList(self.globpropsHash['importfolder']))

    def Esci(self, evt):
        self.Close()
        pass

    def AvviaCostruisciMaster(self, evt):
        self.checkRunning = True
        self.gauge.SetValue(0)
        # self.gauge.setRange(???)

        if os.path.isfile(self.globpropsHash['masterrepository'] + self.globpropsHash['masterrepositoryfilelist']) and \
                self.globpropsHash[
                    'masterrepositoryisready'] == 'True':  # il file elenco esiste ed è completo Costruisci ha finito di girare
            # print("Archivio: "+self.globpropsHash['masterrepository']+" a posto!")
            self.gauge.SetValue(self.gauge.GetRange())
            pass
        else:
            #
            os.chmod(self.globpropsHash['masterrepository'], 0o700)
            if os.path.exists(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"]):
                f = open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'r',
                         encoding="UTF-8")
            else:
                f = open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'x',
                         encoding="UTF-8")
                f.write("")
            for line in f.readlines():
                match = re.search('(^.*)\|(.*$)', line)
                # print("TRACE: "+line)
                self.gauge.SetValue(self.gauge.GetValue() + 1)
                if match is not None:
                    if match[1] not in self.mstrfileHash.keys():
                        self.mstrfileHash[match[1]] = match[2]
            f.close()
            for key in self.mstrfileHash.keys():
                if os.path.exists(key):
                    pass
                else:
                    print(
                        ">>>>>WARNING>>>>>> " + "il file " + key + " non esiste si consiglia di cancellare la riga relativa nel file: ")
                    print(self.globpropsHash['masterrepository'] + "/" + self.globpropsHash['masterrepositoryfilelist'])

            # print("TRACE2: ")
            # print(self.mstrfileHash.values())
            # print(len(self.mstrfileHash))
            self.CostruisciMaster(self.globpropsHash['masterrepository'])
            if self.checkRunning is True:
                # print("File completo")
                self.mstrfileHash.clear()
            self.globpropsHash['masterrepositoryisready'] = True
            self.gauge.SetValue(self.gauge.GetRange())

            # aggiungere qui il popup

            dlg = wx.MessageBox('Costruzione Master Completata', '', wx.OK)
            print(self.mstrfileHash)

            # scrivo nel file True?

    def CostruisciMaster(self, dir="/Users/davideceruti/TestCase/"):
        f = open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'a',
                 encoding="UTF-8")
        # print(str(f))
        for file in os.listdir(dir):
            if os.path.isdir(dir + "/" + file):
                self.CostruisciMaster(dir + "/" + file)
                pass
            else:
                # print(dir+"/"+file)
                fileconpath = dir + "/" + file
                match2 = re.search('^\..*', file)
                if match2 is None:
                    if fileconpath not in self.mstrfileHash.keys():
                        p = subprocess.run('md5 ' + "\'" + dir + "/" + file + "\'", shell=True, universal_newlines=True,
                                           stdout=subprocess.PIPE)
                        match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                        f.writelines(match[1] + "|" + match[2] + "\n")
                        self.gauge.SetValue((self.gauge.GetValue() + 1))
                        PhotoManagerApp.Yield()
            if self.checkRunning is False:
                break
        f.close()

    def CostruisciImport(self, dir="tmp"):
        f2 = open(self.globpropsHash['importfolder'] + "/" + self.globpropsHash["importfilelist"], 'a',
                  encoding="UTF-8")
        # print(str(f))
        for file in os.listdir(dir):
            if os.path.isdir(dir + "/" + file):
                self.CostruisciImport(dir + "/" + file)
                pass
            else:
                # print(dir+"/"+file)
                fileconpath = dir + "/" + file
                match2 = re.search('^\..*', file)
                if match2 is None:
                    if fileconpath not in self.importfileHash.keys():
                        self.gauge.SetValue((self.gauge.GetValue() + 1))
                        self.gauge.Refresh()
                        PhotoManagerApp.Yield()
                        p = subprocess.run('md5 ' + "\"" + dir + "/" + file + "\"", shell=True, universal_newlines=True,
                                           stdout=subprocess.PIPE)

                        PhotoManagerApp.Yield()
                        match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                        f2.writelines(match[1] + "|" + match[2] + "\n")
                        f2.flush()
                        # print("GAUGEVALUE"+str(self.gauge.GetValue()))

                        # PhotoManagerApp.Yield()
            if self.checkRunning is False:
                break
        f2.close()

    def CheckArchive(self, evt):
        self.SelezionaImportFolder(evt)

    def AvviaCopiaFile(self, evt):
        self.AvviaCostruisciMaster(evt)
        self.checkRunning = True
        self.gauge.SetValue(0)
        self.gauge.SetRange(len([name for name in os.listdir(self.globpropsHash['importfolder'])]))
        PhotoManagerApp.Yield()
        if os.path.exists(self.globpropsHash['importfolder'] + "/" + self.globpropsHash["importfilelist"]):
            pass
        else:
            f = open(self.globpropsHash['importfolder'] + "/" + self.globpropsHash["importfilelist"], 'x',
                     encoding="UTF-8")
            f.close()
        self.CopiaFile()
        self.mstrfileHash.clear()
        self.importfileHash.clear()
        self.copyfileHash.clear()
        self.skippedfileHash.clear()
        self.gauge.SetValue(0)
        pass

    def CopiaFile(self):
        # carico hash master
        # scorro albero import
        # calcolo MD5, se chiave esiste lo metto nell'hash degli scarti se no lo metto in quelli da copiare con tutto quello che serve
        # dict key=MD5, valore tupla (path master, "")
        # sbiancare mstrHash
        with open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'r',
                  encoding="UTF-8") as f:

            for line in f.readlines():
                match = re.search('(^.*)\|(.*$)', line)
                if match is None:
                    pass
                    print("<<<ERRORE<<<" + line)
                else:
                    # print(match[2]+">>>"+match[1])
                    if match[2] not in self.mstrfileHash.keys():
                        self.mstrfileHash[match[2]] = match[1]
                    else:
                        self.contatoreDebug += 1
                        print("Ho trovato un duplicato nel master" + str(self.contatoreDebug))
                        print(">>>>>DUPLICATO" + line)
            # print("CaricamentoHashMaster finito")
            # print(self.mstrfileHash.values())
            print("CaricamentoHashMaster finito")

        with open(self.globpropsHash['importfolder'] + "/" + self.globpropsHash["importfilelist"], 'r',
                  encoding="UTF-8") as f:
            for line in f.readlines():
                match = re.search('(^.*)\|(.*$)', line)
                print("TRACE: " + line)
                if match is not None:
                    if match[1] not in self.importfileHash.keys():
                        self.importfileHash[match[1]] = match[2]

        print("Lunghezza HASH import: " + str(len([name for name in os.listdir(self.globpropsHash['importfolder'])])))

        self.CostruisciImport(self.globpropsHash['importfolder'])
        self.gauge.SetValue(self.gauge.GetRange())

        # print("ListaIMPORTCOMPLETATA")
        # print(self.mstrfileHash.values())
        # print("TRACE")
        # print(self.importfileHash.keys())
        for key in self.importfileHash.keys():
            self.importMd5fileHash[self.importfileHash[key]] = key
        print(self.importMd5fileHash.keys())
        # print("TRACCIONE:"+self.importMd5fileHash['5351cb4ea83e83fc0233329ba9e3280e'])

        i = 0
        for md5key in self.importMd5fileHash.keys():
            if md5key in self.mstrfileHash.keys():
                i += 1
                # print("Duplicato"+str(i))
                print(">>>>>DUPLICATO" + self.importMd5fileHash[md5key])
                print(">>>>>DUPLICATO>>>>>>>>>" + self.mstrfileHash[md5key])
                self.skippedfileHash[md5key] = (
                    self.importMd5fileHash[md5key], self.mstrfileHash[md5key], self.mstrfileHash[md5key])
                self.loggingDict[md5key] = ("SKIPPED", self.importMd5fileHash[md5key], self.mstrfileHash[md5key])

            else:
                # self.copyfileHash[md5key]=(os.path.split(self.importMd5fileHash[md5key])[0],os.path.split(self.importMd5fileHash[md5key])[1],time.strftime('%m', ])
                # self.copyfileHash[md5key]=(time.strftime('%m', os.path.getctime(self.importMd5fileHash[md5key])),"ciao")
                print(time.strftime("%b", time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))))
                self.copyfileHash[md5key] = (self.importMd5fileHash[md5key], time.strftime("%b", time.gmtime(
                    os.path.getmtime(self.importMd5fileHash[md5key]))), time.strftime("%Y", time.gmtime(
                    os.path.getmtime(self.importMd5fileHash[md5key]))), "")
                # print(self.copyfileHash[md5key][0],end='')
                # print(self.globpropsHash['masterrepository'], end='')

                srcfile = self.copyfileHash[md5key][0]
                dstdir = self.globpropsHash['masterrepository'] + "/" + self.copyfileHash[md5key][2] + "/" + \
                         self.copyfileHash[md5key][1] + "/"
                dstfile = dstdir + md5key + os.path.splitext(srcfile)[1].lower()

                # print("Nome file da copiare")
                # print(srcfile)
                # print("DSTDIR:")
                # print(dstdir)
                # print("NOMEFILEDESTINAZIONE")
                # print(dstfile)

                if os.path.isdir(dstdir):
                    os.chmod(dstdir, 0o700)
                else:
                    print("DIR PADRE NON SCRIVIBILE: " + str((os.path.dirname(os.path.normpath(dstdir)))))
                    if not os.path.exists(os.path.dirname(os.path.normpath(dstdir))):
                        os.makedirs(os.path.dirname(os.path.normpath(dstdir)), mode=0o700)
                    else:
                        os.chmod(os.path.dirname(os.path.normpath(dstdir)), 0o700)
                    os.makedirs(dstdir, mode=0o700)
                shutil.copy2(srcfile, dstfile, follow_symlinks=False)
                os.chmod(dstfile, 0o400)
                self.loggingDict[md5key] = ("COPIED", self.importMd5fileHash[md5key], dstfile)
                os.chmod(dstdir, 0o500)
                # os.chmod(dstfile,0o444)
                # self.copyfileHash.update(md5key=(self.importMd5fileHash[md5key], time.strftime("%b", time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))), time.strftime("%Y", time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),"OK"))

                # nota che prende md5key come stringa e non come variabile
                # self.copyfileHash.update(md5key=(self.importMd5fileHash[md5key],time.strftime("%b",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),time.strftime("%Y",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),"OK_COPIA"))
                # print("AGGIORNAMENTO HASH")
                # print(md5key)
                # print(self.copyfileHash.items())

        # print("FILE SKIPPATI")
        # print(self.skippedfileHash)
        self.gauge.SetValue(0)
        PhotoManagerApp.Yield()

        for key in self.loggingDict.keys():
            logging.info(str(self.loggingDict[key]))

            # self.loggedCopied.AppendText(self.loggingDict[key][0]+self.loggingDict[key][1]+"\n")


if __name__ == '__main__':
    PhotoManagerApp = wx.App()
    framePrincipale = PhotoManagerAppFrame(None, "PhotoArchiveAnalyzer")
    PhotoManagerApp.MainLoop()
