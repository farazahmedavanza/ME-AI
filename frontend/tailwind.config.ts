import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        avbg: "#0B1220",
        avline: "rgb(30 41 59)",
      },
    },
  },
  plugins: [],
};

export default config;
