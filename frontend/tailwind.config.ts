import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        jarvis: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },
        surface: {
          DEFAULT: "#06060f",
          50: "#0a0a1a",
          100: "#0f0f23",
          200: "#14142b",
          300: "#1a1a35",
          400: "#222245",
          500: "#2a2a55",
        },
        neon: {
          blue: "#00d4ff",
          purple: "#8b5cf6",
          violet: "#6366f1",
          cyan: "#06b6d4",
          pink: "#ec4899",
          green: "#10b981",
          amber: "#f59e0b",
          rose: "#f43f5e",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
        display: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        // Core
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "pulse-slow": "pulseSlow 3s ease-in-out infinite",
        "pulse-fast": "pulseFast 1s ease-in-out infinite",
        "fade-in": "fadeIn 0.5s ease-out",
        "fade-in-up": "fadeInUp 0.6s ease-out",
        "fade-in-down": "fadeInDown 0.4s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "slide-down": "slideDown 0.3s ease-out",
        "slide-in-right": "slideInRight 0.3s ease-out",
        "scale-in": "scaleIn 0.2s ease-out",
        "scale-out": "scaleOut 0.2s ease-in",
        // Holographic
        "scan-line": "scanLine 4s linear infinite",
        "scan-line-fast": "scanLine 2s linear infinite",
        "holographic-shimmer": "holographicShimmer 3s linear infinite",
        "glitch": "glitch 0.3s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "float-delayed": "float 6s ease-in-out 3s infinite",
        // Voice
        "waveform": "waveform 1.5s ease-in-out infinite",
        "waveform-smooth": "waveformSmooth 2s ease-in-out infinite",
        "ring-expand": "ringExpand 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        // Spinner
        "spin-slow": "spin 3s linear infinite",
        "spin-reverse": "spinReverse 4s linear infinite",
        // Breathing
        "breathe": "breathe 4s ease-in-out infinite",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.05)" },
        },
        pulseSlow: {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "0.7" },
        },
        pulseFast: {
          "0%, 100%": { opacity: "0.5" },
          "50%": { opacity: "1" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeInDown: {
          "0%": { opacity: "0", transform: "translateY(-10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideUp: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideDown: {
          "0%": { transform: "translateY(-10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideInRight: {
          "0%": { transform: "translateX(20px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        scaleIn: {
          "0%": { transform: "scale(0.95)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        scaleOut: {
          "0%": { transform: "scale(1)", opacity: "1" },
          "100%": { transform: "scale(0.95)", opacity: "0" },
        },
        scanLine: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        holographicShimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        glitch: {
          "0%, 100%": { transform: "translate(0)" },
          "20%": { transform: "translate(-1px, 1px)" },
          "40%": { transform: "translate(1px, -1px)" },
          "60%": { transform: "translate(-1px, -1px)" },
          "80%": { transform: "translate(1px, 1px)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        waveform: {
          "0%, 100%": { height: "4px" },
          "50%": { height: "20px" },
        },
        waveformSmooth: {
          "0%, 100%": { height: "3px", opacity: "0.3" },
          "25%": { height: "16px", opacity: "0.8" },
          "50%": { height: "24px", opacity: "1" },
          "75%": { height: "10px", opacity: "0.6" },
        },
        ringExpand: {
          "0%": { boxShadow: "0 0 0 0 rgba(0, 212, 255, 0.3)" },
          "70%": { boxShadow: "0 0 0 20px rgba(0, 212, 255, 0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(0, 212, 255, 0)" },
        },
        spinReverse: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(-360deg)" },
        },
        breathe: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.8" },
          "50%": { transform: "scale(1.02)", opacity: "1" },
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "jarvis-grid": "linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px)",
        "holographic": "linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(0, 212, 255, 0.1) 50%, rgba(139, 92, 246, 0.1) 100%)",
        "neon-glow": "linear-gradient(135deg, #6366f1 0%, #00d4ff 50%, #8b5cf6 100%)",
      },
      backgroundSize: {
        "grid-sm": "20px 20px",
        "grid-md": "40px 40px",
        "200%": "200% 100%",
      },
      boxShadow: {
        "neon-blue": "0 0 20px rgba(0, 212, 255, 0.15), 0 0 40px rgba(0, 212, 255, 0.05)",
        "neon-purple": "0 0 20px rgba(139, 92, 246, 0.15), 0 0 40px rgba(139, 92, 246, 0.05)",
        "neon-violet": "0 0 20px rgba(99, 102, 241, 0.2), 0 0 40px rgba(99, 102, 241, 0.1)",
        "glass": "0 8px 32px rgba(0, 0, 0, 0.3)",
        "glass-lg": "0 16px 48px rgba(0, 0, 0, 0.4)",
        "inner-glow": "inset 0 1px 0 rgba(255, 255, 255, 0.05)",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};

export default config;
