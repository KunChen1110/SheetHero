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
      className={`w-full flex items-center p-4 rounded-lg text-left gap-2 bg-(--sh-dark-blue) hover:bg-gray-800/80 border border-(--sh-border-grey) hover:border-(--sh-green) transition-all ${className || ""}`}
    >
      <div className="text-(--sh-white)">{icon}</div>
      <div className="flex-1 text-sm text-(--sh-white)">{title}</div>
    </button>
  );
}
