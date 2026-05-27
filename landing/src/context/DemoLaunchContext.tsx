import { createContext, useCallback, useContext, type ReactNode } from "react";

type DemoLaunchContextValue = {
  startDemo: (company?: string) => void;
};

const DemoLaunchContext = createContext<DemoLaunchContextValue | null>(null);

function clearDemoLaunchCache() {
  Object.keys(sessionStorage)
    .filter((key) => key === "cf_demo_launch" || key.startsWith("cf_demo_loaded_"))
    .forEach((key) => sessionStorage.removeItem(key));
}

export function DemoLaunchProvider({ children }: { children: ReactNode }) {
  const startDemo = useCallback((company = "sandbox") => {
    clearDemoLaunchCache();
    sessionStorage.setItem("cf_demo_launch_pending", company);
    window.location.assign("/dashboard");
  }, []);

  return (
    <DemoLaunchContext.Provider value={{ startDemo }}>
      {children}
    </DemoLaunchContext.Provider>
  );
}

export function useDemoLaunch() {
  const ctx = useContext(DemoLaunchContext);
  if (!ctx) throw new Error("useDemoLaunch must be used within DemoLaunchProvider");
  return ctx;
}
