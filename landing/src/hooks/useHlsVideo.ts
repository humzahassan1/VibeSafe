import { useEffect, useRef } from 'react'
import Hls from 'hls.js'

export function useHlsVideo(src: string) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !src) return

    let hls: Hls | null = null

    if (Hls.isSupported()) {
      hls = new Hls()
      hls.loadSource(src)
      hls.attachMedia(video)
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = src
    }

    return () => {
      hls?.destroy()
    }
  }, [src])

  return videoRef
}
