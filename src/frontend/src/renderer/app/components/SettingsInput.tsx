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
        className={`w-full px-4 py-3 bg-(--sh-dark-blue) border border-(--sh-border-grey) rounded-lg text-(--sh-white) placeholder-(--sh-grey) focus:outline-none focus:border-(--sh-green-highlight) transition-colors
          ${rightElement ? "pr-16" : ""}
          ${className}
        `}
      />
      {rightElement}
    </div>
  );
}
