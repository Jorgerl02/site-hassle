import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

// Warm neutral palette: paper-like background, ink text, a clay accent.
const config = defineConfig({
  globalCss: {
    "html, body": {
      bg: "bg",
      color: "fg",
      fontFamily: "body",
      textRendering: "optimizeLegibility",
    },
  },
  theme: {
    tokens: {
      fonts: {
        heading: { value: "var(--font-serif), Georgia, 'Times New Roman', serif" },
        body: { value: "var(--font-sans), system-ui, -apple-system, 'Segoe UI', sans-serif" },
      },
      colors: {
        sand: {
          50: { value: "#FAF8F4" },
          100: { value: "#F3EFE8" },
          200: { value: "#E8E1D6" },
          300: { value: "#D6CCBD" },
          400: { value: "#B9AC99" },
          500: { value: "#978977" },
          600: { value: "#786C5C" },
          700: { value: "#5C5247" },
          800: { value: "#423B33" },
          900: { value: "#2B2621" },
          950: { value: "#1C1915" },
        },
        clay: {
          50: { value: "#FBF3EE" },
          100: { value: "#F5E2D6" },
          200: { value: "#EBC4AD" },
          300: { value: "#DDA07F" },
          400: { value: "#CC7F58" },
          500: { value: "#B5643F" },
          600: { value: "#9A5132" },
          700: { value: "#7C4029" },
          800: { value: "#5E3121" },
          900: { value: "#41231A" },
          950: { value: "#2A160F" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: "{colors.sand.50}" },
          subtle: { value: "{colors.sand.100}" },
          muted: { value: "{colors.sand.200}" },
          panel: { value: "{colors.white}" },
        },
        fg: {
          DEFAULT: { value: "{colors.sand.950}" },
          muted: { value: "{colors.sand.700}" },
          subtle: { value: "{colors.sand.600}" },
        },
        border: {
          DEFAULT: { value: "{colors.sand.200}" },
          emphasized: { value: "{colors.sand.300}" },
        },
        clay: {
          solid: { value: "{colors.clay.600}" },
          contrast: { value: "{colors.white}" },
          fg: { value: "{colors.clay.700}" },
          muted: { value: "{colors.clay.100}" },
          subtle: { value: "{colors.clay.50}" },
          emphasized: { value: "{colors.clay.200}" },
          focusRing: { value: "{colors.clay.500}" },
        },
        ink: {
          solid: { value: "{colors.sand.950}" },
          contrast: { value: "{colors.sand.50}" },
          fg: { value: "{colors.sand.900}" },
          muted: { value: "{colors.sand.200}" },
          subtle: { value: "{colors.sand.100}" },
          emphasized: { value: "{colors.sand.300}" },
          focusRing: { value: "{colors.sand.700}" },
        },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
