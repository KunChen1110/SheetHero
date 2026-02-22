import { ReactNode } from "react";

// Properties for the settings widget
interface SettingsWidgetProperties {
  icon: ReactNode;
  title: string;
  description: string;
  required?: boolean;
  input: ReactNode;
}

export function SettingsWidget({
  icon,
  title,
  description,
  required,
  input,
}: SettingsWidgetProperties) {
  // HTML for the settings widget
  return (
    <div>
      <label className="flex items-center gap-2 text-sm font-medium text-(--sh-white) py-2">
        <div className="text-(--sh-green-highlight)">{icon}</div>
        {title}
        <div className={required ? "text-(--sh-red)" : "invisible"}>*</div>
      </label>
      <div className="relative">{input}</div>
      <p className="mt-2 text-xs text-(--sh-medium-grey)">{description}</p>
    </div>
  );
}
