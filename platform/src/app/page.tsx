import { Examples } from "@/components/landing/Examples";
import { Faq } from "@/components/landing/Faq";
import { FinalCta } from "@/components/landing/FinalCta";
import { LandingView } from "@/components/landing/LandingView";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Pricing } from "@/components/landing/Pricing";
import { SiteFooter, SiteHeader } from "@/components/landing/SiteHeader";

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <Examples />
        <HowItWorks />
        <Pricing />
        <Faq />
        <FinalCta />
      </main>
      <LandingView />
      <SiteFooter />
    </>
  );
}
