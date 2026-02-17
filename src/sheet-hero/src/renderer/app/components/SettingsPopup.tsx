import { X, Key, Hash, Bot } from "lucide-react";
import { useState, useEffect } from "react";
import { SettingsWidget } from "./SettingsWidget";
import { SettingsInput } from "./SettingsInput";

// Properties needed for the settings popup
interface SettingsPopupProperties {
  isOpen: boolean;
  apiKey: string;
  maxTurns: number;
  baseURL: string;
  model: string;
  onClose: () => void;
  onSave: (
    apiKey: string,
    maxTurns: number,
    model: string,
    baseURL: string,
  ) => void;
}

export function SettingsPopup({
  isOpen,
  apiKey,
  maxTurns,
  baseURL,
  model,
  onClose,
  onSave,
}: SettingsPopupProperties) {
  // If the api key is visible
  const [showApiKey, setShowApiKey] = useState(false);

  // The api key used for the model
  const [localApiKey, setLocalApiKey] = useState(apiKey);

  // The maximum amount of turns the model can perform
  const [localMaxTurns, setLocalMaxTurns] = useState(maxTurns);

  // The model being used
  const [localModel, setLocalModel] = useState(model);

  // The base url being used
  const [localBaseURL, setLocalBaseURL] = useState(baseURL);

  useEffect(() => {
    setLocalApiKey(apiKey);
    setLocalMaxTurns(maxTurns);
    setLocalModel(model);
    setLocalBaseURL(baseURL);
  }, [apiKey, maxTurns, model, baseURL, isOpen]);

  if (!isOpen) return null;

  // Passes arguments to a given "onSave" function, then calls a given "onClose" function
  function handleSave(): void {
    onClose();
    onSave(
      localApiKey.trim(),
      localMaxTurns,
      localModel.trim(),
      localBaseURL.trim(),
    );
  }

  // If clicking off the menu, call the given "onClose" function
  function handleOverlayClick(event: React.MouseEvent): void {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  // HTML for the settings popup
  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-gray-900 border border-gray-700/50 rounded-2xl max-w-md w-full">
        {/* =-=-= Header =-=-= */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800/50">
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors text-gray-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* =-=-= API Key =-=-= */}
          <SettingsWidget
            icon={<Key size={16} />}
            title="API Key"
            description="Required to use SheetHero. Your API key is stored locally."
            required={true}
            input={
              <SettingsInput
                type={showApiKey ? "text" : "password"}
                value={localApiKey}
                onChange={(event) => setLocalApiKey(event.target.value)}
                placeholder="Enter your API key"
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-green-400 transition-colors"
                  >
                    {showApiKey ? "Hide" : "Show"}
                  </button>
                }
              />
            }
          />

          {/* =-=-= Model =-=-= */}
          <SettingsWidget
            icon={<Bot size={16} />}
            title="Model"
            description="Specify the model name (e.g., gpt-4o-mini, gpt-4o, or your local model name)."
            required={true}
            input={
              <SettingsInput
                type="text"
                value={localModel}
                onChange={(event) => setLocalModel(event.target.value)}
                placeholder="e.g., gpt-4o-mini, gpt-4o, local-model"
              />
            }
          />

          {/* =-=-= Max Turns =-=-= */}
          <SettingsWidget
            icon={<Hash size={16} />}
            title="Max Turns"
            description="Maximum number of conversation turns the model can make (1-10)."
            input={
              <SettingsInput
                type="number"
                min="1"
                max="10"
                value={localMaxTurns}
                onChange={(event) =>
                  setLocalMaxTurns(
                    Math.max(1, parseInt(event.target.value) || 1),
                  )
                }
              />
            }
          />

          {/* =-=-= Base URL =-=-= */}
          <SettingsWidget
            icon={<Hash size={16} />}
            title="Base URL"
            description="The root API endpoint used to send model requests."
            input={
              <SettingsInput
                type="string"
                value={localBaseURL}
                onChange={(event) => setLocalBaseURL(event.target.value)}
                placeholder="e.g., https://api.openai.com/v1"
              />
            }
          />
        </div>

        {/* =-=-= Footer =-=-=*/}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-800/50">
          <button
            onClick={onClose}
            className="p-3 rounded-lg text-sm font-medium text-gray-300 hover:bg-gray-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!localApiKey.trim()}
            className="p-3 rounded-lg text-sm font-medium bg-linear-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-green-500 disabled:hover:to-green-600 transition-all"
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
