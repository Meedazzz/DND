const { contextBridge, ipcRenderer } = require('electron');

const bridge = Object.freeze({
  platform: process.platform,
  versions: Object.freeze({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  }),
  saveCampaign: (content, defaultName) => ipcRenderer.invoke('desktop:save-campaign', { content, defaultName }),
  openCampaign: async () => {
    const result = await ipcRenderer.invoke('desktop:open-campaign');
    return result?.canceled ? result : { ...result, data: result.content };
  },
  networkInfo: () => ipcRenderer.invoke('desktop:network-info'),
  getUpdateState: () => ipcRenderer.invoke('desktop:update-state'),
  checkForUpdates: () => ipcRenderer.invoke('desktop:check-update'),
  downloadUpdate: () => ipcRenderer.invoke('desktop:download-update'),
  installUpdate: () => ipcRenderer.invoke('desktop:install-update'),
  openReleases: () => ipcRenderer.invoke('desktop:open-releases'),
  onCommand: (callback) => {
    const listener = (_event, action) => callback(action);
    ipcRenderer.on('desktop:menu', listener);
    return () => ipcRenderer.removeListener('desktop:menu', listener);
  },
  onUpdateStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('desktop:update-status', listener);
    return () => ipcRenderer.removeListener('desktop:update-status', listener);
  }
});

contextBridge.exposeInMainWorld('grimdiceDesktop', bridge);
