import { ReactNode } from "react";

// Properties for the settings input
interface SettingsInputProperties extends React.InputHTMLAttributes<HTMLInputElement> {
  rightElement?: ReactNode;
}

export function SettingsInput({
  rightElement,
  className = "",
  ...props
}: SettingsInputProperties) {
  // HTML for the settings input
  return (
    <div className="relative">
      <input
        {...props}
        className={`w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-green-500/50 transition-colors
          ${rightElement ? "pr-16" : ""}
          ${className}
        `}
      />
      {rightElement}
    </div>
  );
}
