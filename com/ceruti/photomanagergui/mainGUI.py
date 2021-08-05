import logging
import os
import re
import shutil
import subprocess
import time
import wx

#TODO platform indipendence ma prima porting su windows
#TODO scremare immagini e altri tipi di file eventualmente spostando i file uso il comando file?
#TODO aggiungere i log al livello giusto
#TODO GESTIONE ERRORI DA MIGLIORARE
#TODO far capire cosa succede
#TODO IMPOSTARE CORRETTAMENTE I PERMESSI
#TODO cambiare i nomi dei file con vecchionome.nuovonoveconmd5.estensione ??
#TODO sistemare pulsanti e barre di avanzamento
#TODO attenzione a mettere le virgolette a inizio e fine nome file!!!!!
#TODO ancora più importante controllare modalità apertura file (append vs truncate vs readonly)
#TODO mettere il mese in numero
def loadFileExtensionList(self,filepath="/tmp/",extensionList=[],firstcall=True):
    if firstcall is True:
        extensionList=[]
    try:
        for file in os.listdir(filepath):
            if os.path.isdir(filepath+"/"+file):
                loadFileExtensionList(self,filepath+"/"+file,extensionList,False)
                pass
            else:
                ext=os.path.splitext(filepath+"/"+file)
                if ext[1] !="":
                    if ext[1] not in extensionList:
                        extensionList.append(ext[1])
                        logging.debug("Aggiunta "+ext[1]+" alla lista delle estensioni")
                        self.gauge.SetValue(self.gauge.GetValue()+1)
                        if self.gauge.GetValue()>=self.gauge.GetRange():
                            self.gauge.SetValue(0)
    except Exception as e:
        print(e)
    return extensionList

def CheckAndLoadProperties(workingdir='c:\\Users\\Davide\\PycharmProjects\\photoManagerGUI',filenameGlob="default.props",filenameMstr=".masterrepository.conf"):
    myHashGlob={}
    myHashGlob['fileconfprincipale']=filenameGlob
    logging.debug("fileconfprincipale: "+filenameGlob)
    myHashGlob['masterrepositoryconf']=filenameMstr
    with open(os.path.join(workingdir,filenameGlob),encoding="utf-8") as f:
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
    with open(myHashGlob['masterrepository']+'\\'+filenameMstr, encoding="utf-8") as f:
        for line in f.readlines():
            match = re.search('^masterrepositoryfilelist=(.*)', line)
            if match:
                myHashGlob['masterrepositoryfilelist'] = match[1]
            match = re.search('^masterrepositoryisready=(.*)', line)
            if match:
                myHashGlob['masterrepositoryisready'] = match[1]
            match = re.search('^masterrepositorysize=(.*)',line)
            if match:
                myHashGlob['masterrepositorysize']=match[1]
    logging.debug("Dopo caricamento repository: "+str(myHashGlob))
    return myHashGlob

class PhotoManagerAppFrame(wx.Frame):
    def __init__(self,parent,title):
        logging.root.setLevel('DEBUG')
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        max_gauge_size=675
        self.checkRunning=True
        self.globpropsHash=CheckAndLoadProperties("C:\\Users\\c333053\\Downloads","default.props",".masterrepository.conf")
        logging.debug(str(self.globpropsHash))
        self.importDirFileExtensions={}
        self.importfileHash={}
        self.importMd5fileHash={}
        self.mstrfileHash={}
        self.copyfileHash={}
        self.skippedfileHash={}
        self.loggingDict={}
        self.contatoreDebug=0
        self.labelDirList = wx.StaticText(self, label="Import Folder:", pos=(5, 5))
        self.importDirList=wx.GenericDirCtrl(self,pos=(5,25),size=(345,200),style=wx.DIRCTRL_DIR_ONLY)
        self.importDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED,self.SelezionaImportFolder)
        self.avviaCreaListaMaster = wx.Button(self, label="Avvia Creazione Lista File Master", pos=(5, 230), size=(345, -1))
        self.avviaCreaListaMaster.Bind(wx.EVT_BUTTON, self.AvviaCostruisciMaster)
        self.interrompiControllo=wx.Button(self,label="Interrompi",pos=(5, 255), size=(345, -1))
        self.interrompiControllo.Bind(wx.EVT_BUTTON, self.InterrompiFileListCheck)
        self.gauge = wx.Gauge(self, pos=(5, 540),size=(max_gauge_size,-1))
        self.gauge.SetRange(max_gauge_size)
        self.gauge.SetValue(0)
        self.avviaCaricaListaEstensioni = wx.Button(self, label="Mostra estensioni file presenti nel folder Import ", pos=(5, 300))
        self.avviaCaricaListaEstensioni.Bind(wx.EVT_BUTTON, self.AvviaCaricaEstensioni)
        self.avviaCopiaFile = wx.Button(self, label="Avvia Copia File nel Master", pos=(5, 325))
        self.avviaCopiaFile.Bind(wx.EVT_BUTTON, self.AvviaCopiaFile)
        self.esci=wx.Button(self,label="ESCI",pos=(5,450),size=(350,-1))
        self.esci.Bind(wx.EVT_BUTTON,self.Esci)
        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),pos=(355, 25))
        self.loggedCopied = wx.TextCtrl(self,pos=(355, 225))
        self.SetFocus()
        self.loggerFS=logging.getLogger("filesystemstuff")
        self.Center()
        self.Show(True)

    def stringFormattedHash(self):
        result=""
        for k in self.globpropsHash.keys():
            result=result+k+" = "+str(self.globpropsHash[k])+"\n"
        return result

    def SelezionaImportFolder(self,evt):
        self.globpropsHash['importfolder']=self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())

    def AvviaCaricaEstensioni(self,evt):
        self.SelezionaImportFolder(evt)
        messaggioEstensioni=str(loadFileExtensionList(self,self.globpropsHash['importfolder'],True))
        self.gauge.SetValue(self.gauge.GetRange())
        self.messageExtension=wx.MessageBox("Nel folder import ci sono i seguenti tipi di file: \n"+messaggioEstensioni,'',wx.CLOSE)
        logging.info(messaggioEstensioni)
        self.gauge.SetValue(0)

    def Esci(self,evt):
        self.InterrompiFileListCheck(evt)
        self.Close()
        pass

    def AvviaCostruisciMaster(self,evt):
        self.checkRunning = True
        self.gauge.SetValue(0)
        logging.debug("Massimo valore Gauge: "+str(self.gauge.GetRange()))
        self.gauge.Pulse()
        n=self.gauge.GetRange()//4
        if os.path.isfile(self.globpropsHash['masterrepository']+self.globpropsHash['masterrepositoryfilelist']) and self.globpropsHash['masterrepositoryisready']=='True':
            logging.info("L\'archivio: "+self.globpropsHash['masterrepository']+" è a posto!")
            self.gauge.SetValue(self.gauge.GetRange())
            pass
        else:
            os.chmod(self.globpropsHash['masterrepository'], 0o700)
            if os.path.exists(self.globpropsHash['masterrepository'] +'\\'+ self.globpropsHash["masterrepositoryfilelist"]):
                f = open(self.globpropsHash['masterrepository'] + '\\'+self.globpropsHash["masterrepositoryfilelist"], 'r',encoding="UTF-8")
            else:
                f = open(self.globpropsHash['masterrepository'] + '\\'+self.globpropsHash["masterrepositoryfilelist"], 'x',encoding="UTF-8")
                f.write("")
            for line in f.readlines():
                match=re.search('(^.*)\|(.*$)',line)
                matchmd5=re.search('\|([a-f\d]{32}|[A-F\d]{32})',line)
                self.gauge.SetValue(self.gauge.GetValue()+1)
                if matchmd5 is not None:
                    logging.debug('AvviaCostruisciMaster.Md5Hash.VALIDO: '+str(matchmd5[1]))
                    if match is not None:
                        if match[1] not in self.mstrfileHash.keys():
                            n+=1
                            self.mstrfileHash[match[1]]=match[2]
                            logging.info('AvviaCostruisciMaster.AggiuntoFileAllaListaMaster: '+str(match[1]))
                            self.gauge.SetValue(n)
                else:
                    logging.error('AvviaCostruisciMaster.Md5Hash.NON.VALIDO.nellariga: '+line)
            f.close()
            for key in self.mstrfileHash.keys():
                if os.path.exists(key):
                    pass
                else:
                    logging.error("Il file "+key+" non esiste si consiglia di cancellare la riga relativa nel file: "+self.globpropsHash['masterrepository']+"/"+self.globpropsHash['masterrepositoryfilelist'])
            self.CostruisciMaster(self.globpropsHash['masterrepository'])
            for key in self.mstrfileHash.keys():
                logging.debug("File Presente in Archivio: "+key)
            if self.checkRunning is True:
                print("File completo")
                #self.mstrfileHash.clear()
                #da verificare ma forse è questa clear da non fare per avere il master giusto (però se non lo svuoti ci sono un sacco di duplicati che non mi spiego
            self.globpropsHash['masterrepositoryisready']=True
            self.gauge.SetValue(self.gauge.GetRange())
        dlg = wx.MessageBox('Costruzione Master Completata','',wx.OK)
        self.gauge.SetValue(0)

    def CostruisciMaster(self, dir="/Users/davideceruti/TestCase/"):
            f = open(self.globpropsHash['masterrepository']+'\\'+self.globpropsHash["masterrepositoryfilelist"], 'a', encoding="UTF-8")
            for file in os.listdir(dir):
                if os.path.isdir(dir + "\\" + file):
                    self.CostruisciMaster(dir + "\\" + file)
                    pass
                else:
                    fileconpath=dir+"\\"+file
                    match2=re.search('^\..*',file)
                    if match2 is None:
                        if fileconpath not in self.mstrfileHash.keys():
                            md5command='certutil -hashfile ' + dir + '\\' + file + ' MD5'
                            logging.debug('CostruisciMaster: '+md5command)
                            p = subprocess.run(md5command, shell=True,universal_newlines=True,stdout=subprocess.PIPE)
                            #p = subprocess.run('md5 ' + "\"" + dir + "/" + file + "\"", shell=True, universal_newlines=True,
                            #stdout=subprocess.PIPE)
                            #match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                            filerow=dir+'\\'+file+'|'+str(p.stdout).split('\n')[1]+'\n'
                            if p.returncode==0:
                                f.writelines(filerow)
                                logging.info("CostruisciMaster.Scrittura riga: "+filerow)
                            else:
                                logging.error("CostruisciMaster.ERRORE.FILE: "+filerow)
                            #f.writelines(match[1] + "|" + match[2] + "\n")
                            #NB su windows certutil output su più righe-> match non funziona più qui poi non acchiappo il nomefile dall'output del comando tanto lo so già prima
                            self.gauge.SetValue((self.gauge.GetValue() + 1))
                            PhotoManagerApp.Yield()
                if self.checkRunning is False:
                    break
            f.close()


    def CostruisciImport(self,dir="tmp"):
        f2 = open(self.globpropsHash['importfolder'] +"/" +self.globpropsHash["importfilelist"], 'w',
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
                        #p = subprocess.run('md5 ' + "\"" + dir + "/" + file + "\"", shell=True, universal_newlines=True,stdout=subprocess.PIPE)
                        md5command = 'certutil -hashfile ' + dir + '\\' + file + ' MD5'
                        logging.debug(md5command)
                        p = subprocess.run(md5command, shell=True, universal_newlines=True,
                                           stdout=subprocess.PIPE)
                        PhotoManagerApp.Yield()
                        #match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                        filerow = dir + '\\' + file + '|' + str(p.stdout).split('\n')[1] + '\n'
                        f2.writelines(filerow)
                        logging.debug(filerow)
                        f2.flush()
            if self.checkRunning is False:
                break
        f2.close()

    def InterrompiFileListCheck(self,evt):
        self.checkRunning=False

    def AvviaCopiaFile(self,evt):
        #self.AvviaCostruisciMaster(evt)
        #ATTENZIONE, se lanci avvia copia file sia che chiami avviaCostruisciMAster sia che non lo chiami, il master non si aggiorna.
        #DA DECIDERE COsa fare...
        logging.info("CONTROLLONE l'hash mstr ha "+str(len(self.mstrfileHash.items())))
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
        #carico hash master
        #scorro albero import
            #calcolo MD5, se chiave esiste lo metto nell'hash degli scarti se no lo metto in quelli da copiare con tutto quello che serve
        #dict key=MD5, valore tupla (path master, "")
        #sbiancare mstrHash
        with open(self.globpropsHash['masterrepository'] +"/"+ self.globpropsHash["masterrepositoryfilelist"], 'r',
                 encoding="UTF-8") as f:

            for line in f.readlines():
                match = re.search('(^.*)\|(.*$)', line)
                if match is None:
                    pass
                    print("<<<ERRORE<<<"+line)
                else:
                    #print(match[2]+">>>"+match[1])
                    if match[2] not in self.mstrfileHash.keys():
                        self.mstrfileHash[match[2]]=match[1]
                    else:
                        self.contatoreDebug+=1
                        print("Ho trovato un duplicato nel master"+str(self.contatoreDebug))
                        print(">>>>>DUPLICATO"+line)
            #print("CaricamentoHashMaster finito")
            #print(self.mstrfileHash.values())
            print("CaricamentoHashMaster finito")

        with open(self.globpropsHash['importfolder'] + "/"+self.globpropsHash["importfilelist"], 'r',
                     encoding="UTF-8") as f:
            for line in f.readlines():
                match=re.search('(^.*)\|(.*$)',line)
                print("TRACE: "+line)
                if match is not None:
                    if match[1] not in self.importfileHash.keys():
                        self.importfileHash[match[1]]=match[2]

        print("Lunghezza HASH import: "+str(len([name for name in os.listdir(self.globpropsHash['importfolder'])])))

        self.CostruisciImport(self.globpropsHash['importfolder'])
        self.gauge.SetValue(self.gauge.GetRange())

        #print("ListaIMPORTCOMPLETATA")
        #print(self.mstrfileHash.values())
        #print("TRACE")
        #print(self.importfileHash.keys())
        for key in self.importfileHash.keys():
            self.importMd5fileHash[self.importfileHash[key]]=key
        print(self.importMd5fileHash.keys())
        #print("TRACCIONE:"+self.importMd5fileHash['5351cb4ea83e83fc0233329ba9e3280e'])


        i=0
        for md5key in self.importMd5fileHash.keys():
            if md5key in self.mstrfileHash.keys():
                i+=1
                #print("Duplicato"+str(i))
                print(">>>>>DUPLICATO" + self.importMd5fileHash[md5key])
                print(">>>>>DUPLICATO>>>>>>>>>" + self.mstrfileHash[md5key])
                self.skippedfileHash[md5key]=(self.importMd5fileHash[md5key],self.mstrfileHash[md5key],self.mstrfileHash[md5key])
                self.loggingDict[md5key]=("SKIPPED",self.importMd5fileHash[md5key],self.mstrfileHash[md5key])

            else:
                #self.copyfileHash[md5key]=(os.path.split(self.importMd5fileHash[md5key])[0],os.path.split(self.importMd5fileHash[md5key])[1],time.strftime('%m', ])
                #self.copyfileHash[md5key]=(time.strftime('%m', os.path.getctime(self.importMd5fileHash[md5key])),"ciao")
                print(time.strftime("%b",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))))
                self.copyfileHash[md5key]=(self.importMd5fileHash[md5key],time.strftime("%b",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),time.strftime("%Y",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),"")
                #print(self.copyfileHash[md5key][0],end='')
                #print(self.globpropsHash['masterrepository'], end='')


                srcfile=self.copyfileHash[md5key][0]
                dstdir=self.globpropsHash['masterrepository']+"/"+self.copyfileHash[md5key][2]+"/"+self.copyfileHash[md5key][1]+"/"
                dstfile=dstdir+md5key+os.path.splitext(srcfile)[1].lower()

                # print("Nome file da copiare")
                # print(srcfile)
                # print("DSTDIR:")
                # print(dstdir)
                # print("NOMEFILEDESTINAZIONE")
                # print(dstfile)

                if os.path.isdir(dstdir):
                    os.chmod(dstdir,0o700)
                else:
                    print("DIR PADRE NON SCRIVIBILE: "+str((os.path.dirname(os.path.normpath(dstdir)))))
                    if not os.path.exists(os.path.dirname(os.path.normpath(dstdir))):
                        os.makedirs(os.path.dirname(os.path.normpath(dstdir)),mode=0o700)
                    else:
                        os.chmod(os.path.dirname(os.path.normpath(dstdir)), 0o700)
                    os.makedirs(dstdir, mode=0o700)
                shutil.copy2(srcfile,dstfile,follow_symlinks=False)
                os.chmod(dstfile, 0o400)
                self.loggingDict[md5key] = ("COPIED", self.importMd5fileHash[md5key], dstfile)
                os.chmod(dstdir, 0o500)
                #os.chmod(dstfile,0o444)
                #self.copyfileHash.update(md5key=(self.importMd5fileHash[md5key], time.strftime("%b", time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))), time.strftime("%Y", time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),"OK"))


                #nota che prende md5key come stringa e non come variabile
                #self.copyfileHash.update(md5key=(self.importMd5fileHash[md5key],time.strftime("%b",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),time.strftime("%Y",time.gmtime(os.path.getmtime(self.importMd5fileHash[md5key]))),"OK_COPIA"))
                #print("AGGIORNAMENTO HASH")
                #print(md5key)
                #print(self.copyfileHash.items())


        #print("FILE SKIPPATI")
        print(self.skippedfileHash)
        self.gauge.SetValue(0)
        PhotoManagerApp.Yield()
        for key in self.loggingDict.keys():
            logging.info(str(self.loggingDict[key]))
if __name__ == '__main__':
    PhotoManagerApp=wx.App()
    framePrincipale = PhotoManagerAppFrame(None,"PhotoManager")
    PhotoManagerApp.MainLoop()


