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
  "Sube la foto de catálogo y las medidas de tu mueble y recibe un modelo 3D a escala real, listo para tu web y para verlo en casa con realidad aumentada. Lo ves gratis; solo pagas la pieza que descargas.";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: {
    default: `${PRODUCT_NAME}: tu mueble en 3D a escala real desde una foto`,
    template: `%s · ${PRODUCT_NAME}`,
  },
  description,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "es_ES",
    siteName: PRODUCT_NAME,
    title: `${PRODUCT_NAME}: tu mueble en 3D a escala real desde una foto`,
    description,
    url: "/",
    images: [{ url: "/examples/p15-modelo.jpg", width: 720, height: 720, alt: "Modelo 3D de un sillón tapizado" }],
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#FAF8F4",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es" className={`${serif.variable} ${sans.variable}`} suppressHydrationWarning>
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
