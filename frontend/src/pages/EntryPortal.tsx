import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, Sparkles } from 'lucide-react';
import systemLogo from '../assets/logo.png';

export const EntryPortal: React.FC = () => {
  const navigate = useNavigate();
  const [isEntering, setIsEntering] = useState(false);

  const handleEnter = () => {
    setIsEntering(true);
    // Add a slight delay for the exit animation before navigating
    setTimeout(() => {
      navigate('/hub');
    }, 800);
  };

  return (
    <div className="relative w-full h-screen bg-[#f8fafc] overflow-hidden flex flex-col items-center justify-center font-sans">
      {/* Complex Ambient Light Theme Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">

        {/* Base Light Depth Gradients */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,#ffffff_0%,transparent_60%),radial-gradient(ellipse_at_bottom,#f1f5f9_0%,transparent_60%)] opacity-80"></div>

        {/* Glow Core 1 (Avocado Core - Butter Yellow) */}
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.7, 0.5], x: [-30, 30, -30], y: [-20, 20, -20] }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
          style={{ background: 'radial-gradient(circle, rgba(254, 252, 232, 0.6) 0%, transparent 60%)' }}
          className="absolute top-[-20%] left-[-10%] w-[70vw] h-[70vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 2 (Avocado Flesh - Lime Green) */}
        <motion.div
          animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.6, 0.4], x: [30, -10, 30], y: [10, -30, 10] }}
          transition={{ duration: 16, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          style={{ background: 'radial-gradient(circle, rgba(217, 249, 157, 0.4) 0%, transparent 60%)' }}
          className="absolute top-[-10%] right-[10%] w-[60vw] h-[60vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 3 (Avocado Body - Vibrant Emerald) */}
        <motion.div
          animate={{ scale: [0.9, 1.1, 0.9], opacity: [0.5, 0.8, 0.5], x: [20, -20, 20], y: [20, -20, 20] }}
          transition={{ duration: 13, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          style={{ background: 'radial-gradient(circle, rgba(16, 185, 129, 0.2) 0%, transparent 60%)' }}
          className="absolute top-[20%] left-[20%] w-[80vw] h-[80vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 4 (Avocado Skin - Deep Dark Green) */}
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3], x: [-20, 20, -20], y: [-10, 30, -10] }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          style={{ background: 'radial-gradient(circle, rgba(6, 78, 59, 0.15) 0%, transparent 60%)' }}
          className="absolute bottom-[-10%] left-[-10%] w-[90vw] h-[90vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 5 (Avocado Pit - Warm Amber/Wood tone offset) */}
        <motion.div
          animate={{ scale: [0.8, 1.2, 0.8], opacity: [0.4, 0.6, 0.4], x: [10, -30, 10], y: [-20, 20, -20] }}
          transition={{ duration: 17, repeat: Infinity, ease: "easeInOut", delay: 3 }}
          style={{ background: 'radial-gradient(circle, rgba(217, 119, 6, 0.08) 0%, transparent 60%)' }}
          className="absolute bottom-[10%] right-[20%] w-[70vw] h-[70vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 6 (Tech AI Highlight - Soft Mint/Cyan) */}
        <motion.div
          animate={{ scale: [1.1, 0.9, 1.1], opacity: [0.3, 0.6, 0.3], x: [-20, 10, -20], y: [30, -10, 30] }}
          transition={{ duration: 14, repeat: Infinity, ease: "easeInOut", delay: 1.5 }}
          style={{ background: 'radial-gradient(circle, rgba(52, 211, 153, 0.25) 0%, transparent 60%)' }}
          className="absolute bottom-[-20%] right-[-10%] w-[80vw] h-[80vw] rounded-full mix-blend-normal"
        />

        {/* Glow Core 7 (Pure White Glare / Tech focus) */}
        <motion.div
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.7, 0.5], x: [0, 40, 0], y: [0, -40, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 4 }}
          style={{ background: 'radial-gradient(circle, rgba(255, 255, 255, 0.9) 0%, transparent 60%)' }}
          className="absolute top-[40%] left-[40%] w-[50vw] h-[50vw] rounded-full mix-blend-normal"
        />

        {/* Animated Macro-Organism Orbitals */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[140vw] h-[140vw] max-w-[1500px] max-h-[1500px] border-[1px] border-emerald-900/5 rounded-full border-dashed opacity-50 pointer-events-none"
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 45, repeat: Infinity, ease: "linear" }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90vw] h-[90vw] max-w-[900px] max-h-[900px] border-[1px] border-lime-900/10 rounded-full opacity-60 pointer-events-none"
        />

        {/* Parallax Dual-Grid System for complex Moire/interference patterns */}
        <motion.div
          animate={{ backgroundPosition: ["0px 0px", "40px -40px"] }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 opacity-[0.25] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Cpath fill='none' stroke='rgba(16,185,129,0.1)' stroke-width='1' d='M0 39.5h40M39.5 0v40'/%3E%3C/svg%3E")`,
            backgroundSize: '40px 40px',
            WebkitMaskImage: 'radial-gradient(circle_at_50%_0%, black 0%, transparent 60%)'
          }}
        />
        <motion.div
          animate={{ backgroundPosition: ["0px 0px", "-60px 60px"] }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
          className="absolute inset-0 opacity-[0.2] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Cpath fill='none' stroke='rgba(16,185,129,0.15)' stroke-width='1.5' d='M0 59.5h60M59.5 0v60'/%3E%3Ccircle cx='0' cy='0' r='3' fill='rgba(163,230,53,0.2)'/%3E%3C/svg%3E")`,
            backgroundSize: '60px 60px',
            WebkitMaskImage: 'radial-gradient(circle_at_50%_100%, black 0%, transparent 80%)'
          }}
        />

        {/* Intense Luminous Particle System (Hardware Accelerated GPU Rendering) */}
        {[...Array(25)].map((_, i) => (
          <motion.div
            key={`particle-${i}`}
            className="absolute rounded-full pointer-events-none"
            initial={{ 
              top: `${Math.random() * 100}%`, 
              left: `${Math.random() * 100}%`,
              x: 0,
              y: 0,
              scale: 0,
              opacity: 0
            }}
            animate={{
              y: [0, -(Math.random() * 200 + 100)],
              x: [0, Math.random() * 60 - 30],
              opacity: [0, Math.random() * 0.7 + 0.3, 0],
              scale: [0, Math.random() * 1.5 + 0.5, 0]
            }}
            transition={{
              duration: 8 + Math.random() * 10,
              repeat: Infinity,
              ease: "linear", /* Linear is noticeably less CPU heavy than calculating cubic bezier for 25 particles constantly */
              delay: Math.random() * 5
            }}
            style={{
              width: `${Math.random() * 4 + 2}px`,
              height: `${Math.random() * 4 + 2}px`,
              backgroundColor: i % 3 === 0 ? '#10b981' : i % 3 === 1 ? '#a3e635' : '#ffffff',
              boxShadow: `0 0 ${Math.random() * 10 + 5}px ${i % 3 === 0 ? 'rgba(16,185,129,0.8)' : i % 3 === 1 ? 'rgba(163,230,53,0.8)' : 'rgba(255,255,255,0.8)'}`,
              willChange: "transform, opacity"
            }}
          />
        ))}

        {/* Light Vignette Setup (Softly blends edges out) */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_10%,rgba(248,250,252,0.8)_100%)] pointer-events-none"></div>
      </div>

      <AnimatePresence>
        {!isEntering && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.1, filter: "blur(10px)" }}
            transition={{ duration: 0.6, ease: "easeInOut" }}
            className="relative z-10 flex flex-col items-center w-full max-w-4xl px-6"
          >
            {/* Logo Section */}
            <motion.div
              initial={{ y: -50, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
              className="flex flex-col items-center mb-16"
            >
              <div className="relative mb-8 group">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                  className="absolute -inset-4 bg-gradient-to-tr from-emerald-300/30 to-transparent rounded-full blur-2xl group-hover:from-emerald-400/40 transition-colors duration-700"
                />
                <motion.img
                  animate={{ y: [0, -10, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                  src={systemLogo}
                  alt="System Logo"
                  className="relative h-32 w-auto object-contain drop-shadow-[0_0_15px_rgba(16,185,129,0.3)] transition-transform duration-700"
                  style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.05))" }}
                />
              </div>

              <div className="text-center space-y-2">
                <motion.h1
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.5 }}
                  className="text-5xl md:text-6xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-emerald-950 to-emerald-700 drop-shadow-sm"
                >
                  Avocado
                </motion.h1>
                <motion.h2
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.6, delay: 0.8 }}
                  className="text-sm md:text-base font-bold tracking-[0.4em] text-emerald-600 uppercase flex items-center justify-center gap-2"
                >
                  <Sparkles className="w-4 h-4" /> SOP Engine
                </motion.h2>
              </div>
            </motion.div>

            {/* Liquid Glass Start Orb (Avocado Theme) */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: 1, ease: "easeOut" }}
              className="mt-12"
            >
              <div className="relative flex items-center justify-center group">
                {/* Caustic base shadow (Emerald refracting through liquid) */}
                <div className="absolute -bottom-6 w-28 h-6 bg-emerald-400/25 blur-[12px] rounded-full group-hover:bg-emerald-400/40 group-hover:-bottom-8 group-hover:scale-110 transition-all duration-700 pointer-events-none"></div>

                <button
                  onClick={handleEnter}
                  className="relative flex items-center justify-center w-[110px] h-[64px] rounded-full cursor-pointer bg-white/10 hover:bg-white/20 border border-white/60 transition-all duration-700 z-10 hover:-translate-y-2 overflow-hidden"
                  style={{
                    backdropFilter: "blur(25px) saturate(200%)",
                    WebkitBackdropFilter: "blur(25px) saturate(200%)",
                    boxShadow: "inset 0px 8px 16px rgba(255, 255, 255, 0.9), inset 0px -4px 10px rgba(255, 255, 255, 0.5), 0px 10px 25px -8px rgba(16, 185, 129, 0.3)"
                  }}
                  aria-label="Initialize Engine"
                >
                  {/* Internal Liquid Core Glow (Avocado Green fluid) */}
                  <span className="absolute inset-0 w-full h-full bg-[radial-gradient(ellipse_at_50%_120%,rgba(52,211,153,0.5)_0%,transparent_70%)] opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"></span>

                  {/* Surface Liquid Glare */}
                  <span className="absolute top-[2px] left-1/2 -translate-x-1/2 w-[70%] h-[40%] bg-gradient-to-b from-white to-transparent rounded-full opacity-90 pointer-events-none blur-[0.5px]"></span>

                  {/* Core Icon: Glows Emerald on Hover */}
                  <Sparkles className="relative z-10 w-8 h-8 text-slate-400 group-hover:text-emerald-500 transition-colors duration-500 drop-shadow-[0_2px_4px_rgba(0,0,0,0.1)] group-hover:drop-shadow-[0_0_15px_rgba(255,255,255,1)]" strokeWidth={1.75} />
                </button>
              </div>
            </motion.div>

            {/* System Status / Footer text */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 1, delay: 1.5 }}
              className="fixed bottom-8 left-0 right-0 text-center pointer-events-none"
            >
              <p className="text-[12px] font-bold tracking-[0.3em] text-slate-500/90 uppercase">
                Easily create a material matrix
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
