/** 语音输入 Hook - Web Speech API */

import { useState, useCallback, useRef } from "react"

interface UseSpeechInputOptions {
  onResult: (text: string) => void
  lang?: string
}

interface UseSpeechInputReturn {
  isListening: boolean
  isSupported: boolean
  toggleListening: () => void
}

// Web Speech API 类型定义
interface SpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: {
        transcript: string
      }
    }
  }
}

interface SpeechRecognitionInstance {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onend: (() => void) | null
  onerror: ((event: { error: string }) => void) | null
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognitionInstance
    webkitSpeechRecognition: new () => SpeechRecognitionInstance
  }
}

const useSpeechInput = ({
  onResult,
  lang = "zh-CN",
}: UseSpeechInputOptions): UseSpeechInputReturn => {
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)

  const SpeechRecognition =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null

  const isSupported = !!SpeechRecognition

  const toggleListening = useCallback(() => {
    if (!SpeechRecognition) return

    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = lang
    recognition.continuous = true
    recognition.interimResults = false

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.[0]?.transcript
      if (transcript) {
        onResult(transcript)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
    }

    recognition.onerror = () => {
      setIsListening(false)
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [isListening, SpeechRecognition, lang, onResult])

  return { isListening, isSupported, toggleListening }
}

export default useSpeechInput
