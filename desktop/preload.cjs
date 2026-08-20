const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('grimdiceDesktop', {
  isDesktop: true,
  saveCampaign: (data, suggestedName) => ipcRenderer.invoke('save-campaign', { data, suggestedName }),
  openCampaign: () => ipcRenderer.invoke('open-campaign'),
  networkInfo: () => ipcRenderer.invoke('network-info'),
  onCommand: (callback) => {
    const handler = (_event, command) => callback(command);
    ipcRenderer.on('desktop-command', handler);
    return () => ipcRenderer.removeListener('desktop-command', handler);
  }
});
