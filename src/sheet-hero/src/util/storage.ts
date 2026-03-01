import { useState, useEffect } from "react";
import { AppSettings } from "./interfaces";

const SETTINGS_KEY = "app-settings";

// Default settings used in the app
const DEFAULT_SETTINGS: AppSettings = {
  apiKey: "",
  maxTurns: 5,
  baseURL: "",
  model: "gpt-4o-mini",
  outputDir: "",
};

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);

  // Load settings on start.
  useEffect(() => {
    loadSettings();
  }, []);

  // Loads settings from local storage.
  function loadSettings(): void {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY);
      if (saved) {
        const parsed: AppSettings = JSON.parse(saved);
        setSettings(parsed);
        if (!parsed.outputDir) {
          setDefaultDocsPath();
        }
      } else {
        setDefaultDocsPath();
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
    }
  }

  // Sets the output directory to the user's Documents folder
  // but only when there is not one configured.
  function setDefaultDocsPath() {
    window.electronAPI.getDocumentsPath().then((docsPath) => {
      setSettings((prev) => ({
        ...prev,
        outputDir: prev.outputDir || docsPath,
      }));
    });
  }

  // Saves settings to local storage
  function saveSettings(newSettings: AppSettings): void {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));
      setSettings(newSettings);
    } catch (error) {
      console.error("Failed to save settings:", error);
      throw error;
    }
  }

  return {
    settings,
    saveSettings,
  };
}
