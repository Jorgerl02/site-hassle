import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/panel", "/auth/", "/piezas/", "/creditos", "/admin/"] },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
