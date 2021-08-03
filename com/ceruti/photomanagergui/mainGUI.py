import logging
import os
import re
import shutil
import subprocess
import time

import wx


# service PROC
#TODO platform indipendence ma prima porting su windows
#TODO scremare immagini e altri tipi di file eventualmente spostando i file uso il comando file?
#TODO aggiungere i log al livello giusto
#TODO GESTIONE ERRORI DA MIGLIORARE
#TODO far capire cosa succede
#TODO IMPOSTARE CORRETTAMENTE I PERMESSI
#TODO cambiare i nomi dei file con vecchionome.nuovonoveconmd5.estensione
#TODO sistemare pulsanti e barre di avanzamento

def loadFileExtensionList(filepath="/tmp/",extensionList=[],firstcall=True):
    print("FILEPATH A GIRI SUCCESSIVI: "+filepath)
    if firstcall is True:
        extensionList=[]
    try:
        for file in os.listdir(filepath):
            #print(file)
            if os.path.isdir(filepath+"/"+file):
                loadFileExtensionList(filepath+"/"+file,extensionList,False)
                pass
            else:
                #print(dir+"/"+file)
                ext=os.path.splitext(filepath+"/"+file)
                #print(">>>>>>>>"+ext[1])
                if ext[1] !="":
                    if ext[1] not in extensionList:
                        extensionList.append(ext[1])

    except:
        print("something went wrong with reading folders")

    print("PERCHE?"+str(extensionList))
    return extensionList
    pass

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

#INTERFACCIA GRAFICA APPLICAZIONE


class PhotoManagerAppFrame(wx.Frame):
    def __init__(self,parent,title):
        logging.basicConfig(level=logging.DEBUG)
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        self.checkRunning=True
        self.globpropsHash=CheckAndLoadProperties()
        logging.debug(str(self.globpropsHash))

        self.importDirFileExtensions={}
        self.importfileHash={}
        self.importMd5fileHash={}
        self.mstrfileHash={}  #hash di servizio per il caricamento del file parziale

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

        self.gauge = wx.Gauge(self, pos=(5, 560), size=(690, -1))
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
        #print("TRACE5")
        #print(self.globpropsHash.keys())
        for k in self.globpropsHash.keys():
            #print(k)
            #print(self.globpropsHash[k])
            #result=result+self.globpropsHash[k]
            result=result+k+" = "+str(self.globpropsHash[k])+"\n"
        return result

#ACTIONS

    def SelezionaImportFolder(self,evt):
        self.globpropsHash['importfolder']=self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())

    def AvviaCaricaEstensioni(self,evt):
        #self.importDirFileExtensions = loadFileExtensionList(self.globpropsHash['importfolder'])
        self.SelezionaImportFolder(evt)
        print(self.globpropsHash['importfolder'])
        #self.globpropsHash['importfolder'] = self.importDirList.GetPath()

        self.messageExtension=wx.MessageBox("Nel folder import ci sono i seguenti tipi di file: \n"+str(loadFileExtensionList(self.globpropsHash['importfolder'],True)),'',wx.CLOSE)

        #print(loadFileExtensionList(self.globpropsHash['importfolder']))

    def Esci(self,evt):
        self.InterrompiFileListCheck(evt)
        self.Close()
        pass

    def AvviaCostruisciMaster(self,evt):
        self.checkRunning = True
        self.gauge.SetValue(0)
        #self.gauge.setRange(???)

        if os.path.isfile(self.globpropsHash['masterrepository']+self.globpropsHash['masterrepositoryfilelist']) and self.globpropsHash['masterrepositoryisready']=='True':  #il file elenco esiste ed è completo Costruisci ha finito di girare
            print("Archivio: "+self.globpropsHash['masterrepository']+" a posto!")
            self.gauge.SetValue(self.gauge.GetRange())
            pass
        else:
            #
            os.chmod(self.globpropsHash['masterrepository'], 0o700)
            if os.path.exists(self.globpropsHash['masterrepository'] +'\\'+ self.globpropsHash["masterrepositoryfilelist"]):
                f = open(self.globpropsHash['masterrepository'] + '\\'+self.globpropsHash["masterrepositoryfilelist"], 'r',encoding="UTF-8")
            else:
                f = open(self.globpropsHash['masterrepository'] + '\\'+self.globpropsHash["masterrepositoryfilelist"], 'x',encoding="UTF-8")
                f.write("")
            for line in f.readlines():
                match=re.search('(^.*)\|(.*$)',line)
                print("TRACE: "+line)
                self.gauge.SetValue(self.gauge.GetValue()+1)
                if match is not None:
                    if match[1] not in self.mstrfileHash.keys():
                        self.mstrfileHash[match[1]]=match[2]
            f.close()
            for key in self.mstrfileHash.keys():
                if os.path.exists(key):
                    pass
                else:
                    print(">>>>>WARNING>>>>>> "+"il file "+key+" non esiste si consiglia di cancellare la riga relativa nel file: ")
                    print(self.globpropsHash['masterrepository']+"/"+self.globpropsHash['masterrepositoryfilelist'])

            #print("TRACE2: ")
            #print(self.mstrfileHash.values())
            #print(len(self.mstrfileHash))
            self.CostruisciMaster(self.globpropsHash['masterrepository'])
            if self.checkRunning is True:
                #print("File completo")
                self.mstrfileHash.clear()
            self.globpropsHash['masterrepositoryisready']=True
            self.gauge.SetValue(self.gauge.GetRange())

            #aggiungere qui il popup

            dlg = wx.MessageBox('Costruzione Master Completata','',wx.OK)
            print(self.mstrfileHash)

            #scrivo nel file True?
    def CostruisciMaster(self, dir="/Users/davideceruti/TestCase/"):
            f = open(self.globpropsHash['masterrepository']+'\\'+self.globpropsHash["masterrepositoryfilelist"], 'a', encoding="UTF-8")
            #print(str(f))
            for file in os.listdir(dir):
                if os.path.isdir(dir + "\\" + file):
                    self.CostruisciMaster(dir + "\\" + file)
                    pass
                else:
                    #print(dir+"/"+file)
                    fileconpath=dir+"\\"+file
                    match2=re.search('^\..*',file)
                    if match2 is None:
                        if fileconpath not in self.mstrfileHash.keys():

                            #
                            #MD5 hash di D:\ArchivioFoto\2000\Aug\006d7fbd3a92260bbc28cfa812c92b56.jpg:
                            #006d7fbd3a92260bbc28cfa812c92b56
                            #CertUtil: - Esecuzione comando hashfile riuscita.
                            #
                            md5command='certutil -hashfile ' + dir + '\\' + file + ' MD5'
                            logging.debug(md5command)
                            p = subprocess.run(md5command, shell=True,universal_newlines=True,stdout=subprocess.PIPE)
                            #p = subprocess.run('md5 ' + "\"" + dir + "/" + file + "\"", shell=True, universal_newlines=True,
                            #stdout=subprocess.PIPE)
                            #match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                            filerow=dir+'\\'+file+'|'+str(p.stdout).split('\n')[1]+'\n'
                            f.writelines(filerow)
                            logging.debug(filerow)
                            #f.writelines(match[1] + "|" + match[2] + "\n")
                            #NB su windows certutil output su più righe-> match non funziona più qui poi non acchiappo il nomefile dall'output del comando tanto lo so già prima
                            self.gauge.SetValue((self.gauge.GetValue() + 1))
                            PhotoManagerApp.Yield()
                if self.checkRunning is False:
                    break
            f.close()


    def CostruisciImport(self,dir="tmp"):
        f2 = open(self.globpropsHash['importfolder'] +"/" +self.globpropsHash["importfilelist"], 'a',
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
                        #filename = match[1]
                        #md5code = match[2]
                        filerow = dir + '\\' + file + '|' + str(p.stdout).split('\n')[1] + '\n'
                        f2.writelines(filerow)
                        logging.debug(filerow)
                        #f2.writelines(filename + "|" + md5code + "\n")
                        f2.flush()
                        #print("GAUGEVALUE"+str(self.gauge.GetValue()))
                        #MD5(tesinaFrancesco.key) = 8025068626c71ef8fe6853e361244b66
                        #PhotoManagerApp.Yield()
            if self.checkRunning is False:
                break
        f2.close()

    def InterrompiFileListCheck(self,evt):
        self.checkRunning=False

    def AvviaCopiaFile(self,evt):
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
        #carico hash master
        #scorro albero import
            #calcolo MD5, se chiave esiste lo metto nell'hash degli scarti se no lo metto in quelli da copiare con tutto quello che serve
        #dict key=MD5, valore tupla (path master, "")
        #sbiancare mstrHash
        with open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'r',
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

            #self.loggedCopied.AppendText(self.loggingDict[key][0]+self.loggingDict[key][1]+"\n")






if __name__ == '__main__':
    #main ()

    PhotoManagerApp=wx.App()
    framePrincipale = PhotoManagerAppFrame(None,"PhotoManager")
    PhotoManagerApp.MainLoop()




    # framePrincipaleImport=wx.Frame(None,title="PhotoManager",pos=p1)
    # framePrincipaleMasterRepository=wx.Frame(None,title="PhotoManager")
    # changeImportingFolder=wx.Button(framePrincipaleImport,label="Cambia",)
    # changeMasterRepository=wx.Button(framePrincipaleMasterRepository,label="Cambia2")
    #
    #
    #
    #
    # framePrincipaleImport.Show()
    # framePrincipaleMasterRepository.Show()

    #label = wx.StaticText(panel, label="Hello World", pos=(100, 50))
    #PROPRIETA gestite:
    #importfolder
    #masterrepository

