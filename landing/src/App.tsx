import { Navbar } from "./components/Navbar";
import { Background } from "./components/Background";
import { Hero } from "./components/Hero";
import { ProductPreview } from "./components/ProductPreview";
import { Features } from "./components/Features";
import { HowItWorks } from "./components/HowItWorks";
import { DemoWorkspaces } from "./components/DemoWorkspaces";
import { VideoSection } from "./components/VideoSection";
import { Founder } from "./components/Founder";
import { Contact } from "./components/Contact";
import { Faq } from "./components/Faq";
import { FinalCta } from "./components/FinalCta";
import { useEffect } from "react";
import { DemoLaunchProvider } from "./context/DemoLaunchContext";
import { CommerceFlowAssistant } from "./components/CommerceFlowAssistant";
import { CommerceFlowFeedback } from "./components/CommerceFlowFeedback";
import { trackUsage } from "./utils/trackUsage";

export default function App() {
  useEffect(() => {
    trackUsage("landing_view", "/");
  }, []);

  return (
    <DemoLaunchProvider>
      <Background />
      <Navbar />
      <main className="relative">
        <Hero />
        <ProductPreview />
        <Features />
        <HowItWorks />
        <DemoWorkspaces />
        <VideoSection />
        <Founder />
        <Contact />
        <Faq />
        <FinalCta />
      </main>
      <CommerceFlowFeedback />
      <CommerceFlowAssistant />
    </DemoLaunchProvider>
  );
}
