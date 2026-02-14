import { ReactNode } from "react";

// Properties needed for the sidebar widget
interface SidebarWidgetProperties {
  onWidgetClick: () => void;
  icon: ReactNode;
  title: string;
  className?: string;
}

export function SidebarWidget({
  onWidgetClick,
  icon,
  title,
  className,
}: SidebarWidgetProperties) {
  // HTML for the sidebar widget
  return (
    <button
      onClick={onWidgetClick}
      className={`w-full flex items-center p-4 rounded-lg text-left gap-2 bg-gray-900 hover:bg-gray-800/80 border border-gray-700/50 hover:border-green-600/20 transition-all ${className || ""}`}
    >
      {icon}
      <div className="flex-1 text-sm text-gray-200">{title}</div>
    </button>
  );
}
