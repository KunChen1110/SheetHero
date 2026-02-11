interface MissingAPIProperties {
  onSettingsClick: () => void;
}

export function MissingAPI({ onSettingsClick }: MissingAPIProperties) {
  return (
    <div className="bg-linear-to-r from-yellow-900/40 to-red-900/40 border-b border-yellow-600/30 backdrop-blur-sm rounded-3xl">
      <div className="max-w-4xl mx-auto p-5">
        <div className="flex items-start">
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-yellow-200">
              API Key Required
            </h3>
            <p className="text-sm text-yellow-100/80 py-2">
              Please configure your API key in settings to start usings
              SheetHero.
            </p>
            <button
              onClick={onSettingsClick}
              className="p-3 bg-yellow-600 hover:bg-yellow-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg"
            >
              Open Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
