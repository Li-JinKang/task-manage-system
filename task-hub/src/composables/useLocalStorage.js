import { ref } from 'vue'

export function useLocalStorage(key, defaultValue = null) {
  const data = ref(defaultValue)
  return data
}
