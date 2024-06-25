#!/usr/bin/python
import wx

class CPFSFrame(wx.Frame):
    def __init__(self, parent, title):
        super(CPFSFrame, self).__init__(parent, title=title,
                                    style = wx.BORDER | wx.CAPTION | wx.SYSTEM_MENU | wx.CLOSE_BOX,
                                    size=(350, 200))
        panel = wx.Panel(self, -1)

        pNumberLabel = wx.StaticText(panel, -1, 'Project number: ')
        pNumberText = wx.TextCtrl(panel, -1, '', size=(175, -1))
        pNumberText.SetInsertionPoint(0)

        pNameLabel = wx.StaticText(panel, -1, 'Project name: ')
        pNameText = wx.TextCtrl(panel, -1, '', size=(175, -1))
        pNameText.SetInsertionPoint(0)

        pButton = wx.Button(panel, label='Create')
        pButton.Bind(wx.EVT_BUTTON, self.OnCreate)

        sizer = wx.FlexGridSizer(cols=2, hgap=6, vgap=6)
        sizer.AddMany([pNumberLabel, pNumberText, pNameLabel, pNameText, pButton])
        panel.SetSizer(sizer)

        statusBar = self.CreateStatusBar()
        self.Show()
    def OnCreate(self, evt):
        self.Close(True)

        self.Centre()
        self.Show()

if __name__ == '__main__':
    app = wx.App()
    CPFSFrame(None, title='Create New Project Folder Structure')
    app.MainLoop()