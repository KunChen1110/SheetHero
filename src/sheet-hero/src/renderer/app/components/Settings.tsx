import { X, Key, Hash, Bot } from "lucide-react";
import { useState, useEffect } from "react";

interface SettingsProperties {
  isOpen: boolean;
  apiKey: string;
  maxTurns: number;
  model: string;
  onClose: () => void;
  onSave: (apiKey: string, maxTurns: number, model: string) => void;
}

export function Settings({
  isOpen,
  apiKey,
  maxTurns,
  model,
  onClose,
  onSave,
}: SettingsProperties) {
  const [localApiKey, setLocalApiKey] = useState(apiKey);
  const [localMaxTurns, setLocalMaxTurns] = useState(maxTurns);
  const [showApiKey, setShowApiKey] = useState(false);
  const [localModel, setLocalModel] = useState(model);

  useEffect(() => {
    setLocalApiKey(apiKey);
    setLocalMaxTurns(maxTurns);
  }, [apiKey, maxTurns, model, isOpen]);

  if (!isOpen) return null;

  function handleSave(): void {
    onSave(localApiKey.trim(), localMaxTurns, localModel.trim());
    onClose();
  }

  function handleOverlayClick(e: React.MouseEvent): void {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-gray-900 border border-gray-700/50 rounded-2xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800/50">
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors text-gray-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* API Key */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-200 py-2">
              <Key size={16} className="text-green-400" />
              API Key
              <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={localApiKey}
                onChange={(e) => setLocalApiKey(e.target.value)}
                placeholder="Enter your API key"
                className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-green-500/50 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-green-400 transition-colors"
              >
                {showApiKey ? "Hide" : "Show"}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Required to use SheetHero. Your API key is stored locally.
            </p>
          </div>

          {/* Model */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-200 mb-2">
              <Bot size={16} className="text-green-400" />
              Model
              <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={localModel}
              onChange={(e) => setLocalModel(e.target.value)}
              placeholder="e.g., gpt-4-mini, gpt-4o, local-model"
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-green-500/50 transition-colors"
            />
            <p className="mt-2 text-xs text-gray-500">
              Specify the model name (e.g., gpt-4-mini, gpt-4o, or your local
              model name).
            </p>
          </div>

          {/* Max Turns */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-gray-200 mb-2">
              <Hash size={16} className="text-green-400" />
              Max Turns
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={localMaxTurns}
              onChange={(e) =>
                setLocalMaxTurns(Math.max(1, parseInt(e.target.value) || 1))
              }
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-green-500/50 transition-colors"
            />
            <p className="mt-2 text-xs text-gray-500">
              Maximum number of conversation turns the model can make (1-10).
            </p>
          </div>
        </div>

        {/* Footer */}
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
