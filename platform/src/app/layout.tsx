import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";
import type { ReactNode } from "react";
import { Analytics } from "@/components/Analytics";
import { CookieConsent } from "@/components/CookieConsent";
import { EmotionRegistry } from "@/components/ui/emotion-registry";
import { Provider } from "@/components/ui/provider";
import { PRODUCT_NAME, siteUrl } from "@/lib/site";
import "./globals.css";

const serif = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["500"],
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const description =
  "Photo to 3D model for furniture: upload a catalogue photo and the dimensions and get a true-to-scale 3D model for your website and AR. No credit card required; you only pay for the pieces you download.";

const title = `Photo to 3D model for furniture, true to scale with AR · ${PRODUCT_NAME}`;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: title,
    template: `%s · ${PRODUCT_NAME}`,
  },
  description,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "en_GB",
    siteName: PRODUCT_NAME,
    title,
    description,
    url: "/",
    images: [{ url: "/examples/p15-modelo.jpg", width: 720, height: 720, alt: "3D model of an upholstered armchair" }],
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#FAF8F4",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`} suppressHydrationWarning>
      <body>
        <EmotionRegistry>
          <Provider>
            {children}
            <CookieConsent />
          </Provider>
        </EmotionRegistry>

        <Analytics />
      </body>
    </html>
  );
}
