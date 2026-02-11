import { useState, useEffect } from "react";
import { AppSettings } from "./interfaces";

const SETTINGS_KEY = "app-settings";

// Default settings used in the app
const DEFAULT_SETTINGS: AppSettings = {
  apiKey: "",
  maxTurns: 3,
  model: "gpt-4o-mini",
};

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);

  // Load settings on start
  useEffect(() => {
    loadSettings();
  }, []);

  // Loads settings from local storage
  function loadSettings(): void {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY);
      if (saved) {
        setSettings(JSON.parse(saved));
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
    }
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
