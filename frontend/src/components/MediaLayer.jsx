import { useEffect, useRef } from "react";

// Shows the host's image and plays the host's sound.
// media looks like { id: 1717, type: "image" | "sound", src: "..." } or null.
export default function MediaLayer({ media, audioReady }) {
    const id = media?.id;
    const type = media?.type;
    const src = media?.src;

    const audioRef = useRef(null);
    // A sound that was already set when this page opened counts as old news.
    const handledRef = useRef(id);

    // Play each NEW sound once. The id changes with every send, so the host
    // can play the same file twice in a row.
    useEffect(() => {
        if (handledRef.current === id) return;
        handledRef.current = id;
        if (!audioReady || type !== "sound") return;
        audioRef.current?.pause();
        const audio = new Audio(src);
        audioRef.current = audio;
        audio.play().catch(() => {}); // blocked autoplay must not crash
        }, [id, type, src, audioReady]);
        
        // Clearing the screen or showing an image stops any sound still playing.
        useEffect(() => {
            if (type !== "sound") audioRef.current?.pause();
        }, [type]);
        
        if (type === "image") {
            return (
                <div className="media">
                    <img src={src} alt="" />
                </div>
            );
        }
    return null;
}