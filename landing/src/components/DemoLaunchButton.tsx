import type { ReactNode } from "react";
import { useDemoLaunch } from "../context/DemoLaunchContext";

type Props = {
  children: ReactNode;
  className?: string;
  company?: string;
};

export function DemoLaunchButton({ children, className = "btn-primary", company = "atlas" }: Props) {
  const { startDemo } = useDemoLaunch();
  return (
    <button type="button" className={className} onClick={() => startDemo(company)}>
      {children}
    </button>
  );
}
