import { AlertCircle, Settings } from "lucide-react";

// Properties needed for the app api overlay
interface AppAPIOverlayProperties {
  onSettingsClick: () => void;
}

export function AppAPIOverlay({ onSettingsClick }: AppAPIOverlayProperties) {
  // HTML for the app api overlay
  return (
    <div className="bg-linear-to-r from-(--sh-red)/20 to-(--sh-red)/30 border-b border-(--sh-red)/30 backdrop-blur-sm rounded-3xl">
      <div className="max-w-4xl mx-auto p-5">
        <div className="flex items-start gap-2">
          <AlertCircle size={20} className="text-(--sh-red)" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-(--sh-white)">
              API Key Required
            </h3>
            <p className="text-sm text-(--sh-grey) py-2">
              Please configure your API key in settings to start usings
              SheetHero.
            </p>
            <button
              onClick={onSettingsClick}
              className="p-3 bg-(--sh-red) hover:bg-(--sh-red)/80 text-(--sh-white) text-sm rounded-lg transition-colors items-center inline-flex gap-2"
            >
              <Settings size={16} />
              Open Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
