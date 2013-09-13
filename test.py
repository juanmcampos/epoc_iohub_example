from psychopy import visual, core
win=visual.Window([400,400])
channelNames = ["F3", "FC5", "AF3", "F7", "T7", "P7", "O1","O2", "P8",  "T8",  "F8", "AF4","FC6","F4"]
channelStims = {}
i=-1

for channel in channelNames:
    print channel
    stim = visual.Circle(win, 0.5, pos=(i,i), fillColor='red')
    stim.setAutoDraw(True)
    channelStims[channel]=stim
    i+=0.1

print channelStims
message = visual.TextStim(win, text='hello')
message.setAutoDraw(True)#automatically draw every frame
win.flip()
core.wait(2.0)
message.setText('world')#change properties of existing stim
win.flip()
core.wait(2.0)

