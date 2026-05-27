import { motion } from "framer-motion";

export function Background() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="absolute inset-0 bg-mesh" />
      <motion.div
        className="absolute -right-[18%] top-[-12%] h-[55vh] w-[55vh] rounded-full bg-indigo-500/16 blur-[130px]"
        animate={{ x: [0, 24, 0], y: [0, 16, 0], opacity: [0.28, 0.42, 0.28] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -left-[15%] top-[30%] h-[45vh] w-[45vh] rounded-full bg-blue-700/12 blur-[110px]"
        animate={{ x: [0, -20, 0], opacity: [0.22, 0.34, 0.22] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[-15%] left-[35%] h-[40vh] w-[50vh] rounded-full bg-sky-900/14 blur-[120px]"
        animate={{ y: [0, -16, 0], opacity: [0.18, 0.28, 0.18] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0b1020]/24 to-[#0b1020]/80" />
    </div>
  );
}
