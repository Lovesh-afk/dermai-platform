import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        porcelain: "#FAF7F2",
        ink: {
          DEFAULT: "#20281F",
          soft: "#4B564A",
        },
        pine: {
          50: "#EEF4F1",
          100: "#D7E5DE",
          200: "#AFCBBC",
          300: "#82AC97",
          400: "#548A70",
          500: "#376F58",
          600: "#2F5D50",
          700: "#254A40",
          800: "#1C3931",
          900: "#132A24",
        },
        ochre: {
          50: "#FBF3E4",
          100: "#F3E0B8",
          200: "#E9CB8A",
          300: "#DEB35C",
          400: "#D3A144",
          500: "#C9973C",
          600: "#B07F2E",
          700: "#8A6222",
          800: "#634518",
          900: "#3F2C0E",
        },
        sage: {
          50: "#F7F9F6",
          100: "#E4E9DE",
          200: "#CFD9C6",
          300: "#B2C1A5",
        },
        alert: {
          DEFAULT: "#B3423A",
          soft: "#F3DEDB",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      borderRadius: {
        card: "14px",
      },
    },
  },
  plugins: [],
};
export default config;