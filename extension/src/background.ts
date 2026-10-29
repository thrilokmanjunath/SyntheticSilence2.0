// Service worker: right-click menu and keyboard shortcut. Analysis itself runs in the panel
// (see api.ts), so no request depends on this worker staying alive.
import { COMMAND_ID, handleMenuClick, handleShortcut, MENU_ID, type WorkerDeps } from './handoff.js';
import { readPageSelection } from './inject.js';

const deps: WorkerDeps = {
  openPanel: (target) => {
    // Must be called straight from the user gesture, before any await.
    if (target.tabId !== undefined) return chrome.sidePanel.open({ tabId: target.tabId });
    if (target.windowId !== undefined) return chrome.sidePanel.open({ windowId: target.windowId });
    return Promise.resolve();
  },
  store: (key, value) => chrome.storage.session.set({ [key]: value }),
  readSelection: async (tabId) => {
    const [injected] = await chrome.scripting.executeScript({ target: { tabId }, func: readPageSelection });
    return typeof injected?.result === 'string' ? injected.result : '';
  },
  now: () => Date.now(),
};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: 'Check evidence for “%s”',
      contexts: ['selection'],
    });
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID) return;
  void handleMenuClick(info.selectionText, tab, deps);
});

chrome.commands.onCommand.addListener((command, tab) => {
  if (command !== COMMAND_ID) return;
  void handleShortcut(tab, deps);
});
