import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTaskStore = defineStore('task-store', () => {
  const tasks = ref([])
  const filter = ref('all')

  const filteredTasks = computed(() => tasks.value)

  return {
    tasks,
    filter,
    filteredTasks,
  }
})
