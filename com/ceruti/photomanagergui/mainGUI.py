import wx
import os
import re
import unittest
import subprocess
from filecmp import dircmp

def loadProperties(filename="default.props"):
    globpropsHash={}
    if os.path.exists(filename):
        f=open(filename,encoding="utf-8")
        for line in f.readlines():
            m = re.search('\^#', line)
            if m:
                #print(line)
                pass
            else:
                m=re.search('.+#',line)
                if not m:
                    m=re.search('(.+)=(.+)',line)

                    if m:
                        globpropsHash[m.group(1)]=m.group(2)
                    pass
                else:
                    pass
        if len(globpropsHash)>0:
            return globpropsHash
        else:
            return {}
    else:
        return None

def testLoadProperties():
    test = unittest.TestCase()
    test.assertEqual(loadProperties("default.props"), {'masterrepository': '/tmp/'})
    test.assertEqual(loadProperties("default2.props"), {'masterrepository': '/Volumes/TOSHIBA/MASTERFoto/'})
    test.assertEqual(loadProperties("default3.props"), {'masterrepository': '/Volumes/TOSHIBA/MASTERFoto/',
                                                        'importfolder': '/Volumes/TOSHIBA/FotoStaging'})
    test.assertEqual(loadProperties("default4.props"), {'masterrepository': '/Volumes/TOSHIBA/MASTERFoto/'})
    test.assertEqual(loadProperties("default5.props"), {'a':'b'})
    test.assertEqual(loadProperties("default6.props"), {})
    test.assertEqual(loadProperties("default7.props"), None)

def CheckAndLoadProperties(filenameGlob="default.props",filenameMstr=".masterrepository.conf"):
    myHashGlob={}
    myHashGlob['fileconfprincipale']=filenameGlob
    myHashGlob['masterrepositoryconf']=filenameMstr
    if os.path.exists(filenameGlob):
        f=open(filenameGlob,encoding="utf-8")
        for line in f.readlines():
            #print(line)
            match = re.search('^masterrepository=(.*)', line)
            #print(match)
            if match:
                myHashGlob['masterrepository']=match[1]
            match = re.search('^importfolder=(.*)', line)
            if match:
                myHashGlob['importfolder']=match[1]
        f.close()
        #print(myHashGlob)
        #print(">>>>>>>")
        #print(myHashGlob['masterrepository']+filenameMstr)
        if os.path.exists(myHashGlob['masterrepository']+filenameMstr):
            f = open(myHashGlob['masterrepository']+filenameMstr, encoding="utf-8")
            #print("file aperto")
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
            f.close()
        #print(myHashGlob)
    return myHashGlob











class PhotoManagerAppFrame(wx.Frame):
    def __init__(self,parent,title):
        wx.Panel.__init__(self, parent, title=title, size=(700, 600))
        self.checkRunning=True
        self.globpropsHash=CheckAndLoadProperties()

        self.labelDirList = wx.StaticText(self, label="Import Folder:", pos=(5, 5))
        self.importDirList=wx.GenericDirCtrl(self,pos=(5,25),size=(345,200),style=wx.DIRCTRL_DIR_ONLY)
        self.importDirList.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED,self.SelezionaImportFolder)


#        self.textMasterRepository = wx.TextCtrl(self, pos=(355, 25), value=self.globpropsHash["masterrepository"], size=(350, -1))
#        self.changeMasterRepository = wx.Button(self, label="Cambia Master Repository Folder", pos=(355, 55))


        # self.avviaControllo = wx.Button(self, label="Avvia Controllo Duplicati", pos=(5, 300), size=(350, -1))
        # self.avviaControllo.Bind(wx.EVT_BUTTON, self.CheckFileList)
        self.interrompiControllo=wx.Button(self,label="Interrompi",pos=(5, 255), size=(345, -1))
        self.interrompiControllo.Bind(wx.EVT_BUTTON, self.InterrompiFileListCheck)


        self.gauge = wx.Gauge(self, pos=(5, 275), size=(345, -1))

        self.esci=wx.Button(self,label="ESCI",pos=(5,450),size=(350,-1))
        self.esci.Bind(wx.EVT_BUTTON,self.Esci)

        self.propertyList = wx.StaticText(self, label="Parametri caricati: \n" + self.stringFormattedHash(),pos=(355, 25))
        self.SetFocus()

        self.avviaCreaListaMaster = wx.Button(self, label="Avvia Creazione Lista File Master", pos=(5, 230), size=(345, -1))
        self.avviaCreaListaMaster.Bind(wx.EVT_BUTTON, self.AvviaCostruisciMaster)

        #strutture dati per preparare la copia dei file
        #self.importfileHash={}
        self.mstrfileHash={}
        self.Center()
        self.Show(True)

    def SelezionaImportFolder(self,evt):
        self.globpropsHash['importfolder']=self.importDirList.GetPath()
        self.propertyList.SetLabel("Parametri caricati: \n" + self.stringFormattedHash())

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

    def Esci(self,evt):
        self.InterrompiFileListCheck(evt)
        self.Close()
        pass

    def AvviaCostruisciMaster(self,evt):
        self.checkRunning=True
        if os.path.isfile(self.globpropsHash['masterrepository']+self.globpropsHash['masterrepositoryfilelist']) and self.globpropsHash['masterrepositoryisready']=='True':  #il file elenco esiste ed è completo Costruisci ha finito di girare
            #print("Archivio: "+self.globpropsHash['masterrepository']+" a posto!")
            pass
        else:
            #
            f = open(self.globpropsHash['masterrepository'] + self.globpropsHash["masterrepositoryfilelist"], 'r',
                     encoding="UTF-8")
            for line in f.readlines():
                match=re.search('(^.*)\|(.*$)',line)
                #print("TRACE: "+line)
                if match is not None:
                    if match[1] not in self.mstrfileHash.keys():
                        self.mstrfileHash[match[1]]=match[2]
            f.close()
            #print("TRACE2: ")
            #print(self.mstrfileHash.values())
            #print(len(self.mstrfileHash))
            self.CostruisciMaster(self.globpropsHash['masterrepository'])
            if self.checkRunning is True:
                #print("File completo")
                self.mstrfileHash.clear()
            self.globpropsHash['masterrepositoryisready']=True
            #scrivo nel file True?

    def CostruisciMaster(self, dir="/Users/davideceruti/TestCase/"):
            f = open(self.globpropsHash['masterrepository']+self.globpropsHash["masterrepositoryfilelist"], 'a', encoding="UTF-8")
            #print(str(f))
            for file in os.listdir(dir):
                if os.path.isdir(dir + "/" + file):
                    self.CostruisciMaster(dir + "/" + file)
                    pass
                else:
                    #print(dir+"/"+file)
                    fileconpath=dir+"/"+file
                    match2=re.search('^\..*',file)
                    if match2 is None:
                        if fileconpath not in self.mstrfileHash.keys():
                            p = subprocess.run('md5 ' + "\"" + dir + "/" + file + "\"", shell=True, universal_newlines=True,
                            stdout=subprocess.PIPE)
                            match = re.search("MD5 \((.*)\) = (.*)", str(p.stdout))
                            f.writelines(match[1]+"|"+match[2]+"\n")
                            self.gauge.SetValue((self.gauge.GetValue() + 1))
                            PhotoManagerApp.Yield()
                if self.checkRunning is False:
                    break
            f.close()

    def InterrompiFileListCheck(self,evt):
        self.checkRunning=False

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

