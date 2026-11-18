<script setup>
import { storeToRefs } from 'pinia'
import { useTaskStore } from '@/stores/taskStore'
import TaskHeader from '@/components/TaskHeader.vue'
import TaskInput from '@/components/TaskInput.vue'
import TaskFilter from '@/components/TaskFilter.vue'
import TaskItem from '@/components/TaskItem.vue'

// 初始化仓库
const taskStore = useTaskStore()
// 使用 storeToRefs 保持数据的响应式解构
// 这样在模板里可以直接用 filter 和 filteredTasks
const { filter, filteredTasks } = storeToRefs(taskStore)
const { addTask, removeTask, toggleTask } = taskStore
</script>

<template>
  <div class="py-12 px-4">
    <div class="max-w-md mx-auto bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">
      <TaskHeader />
      <main class="p-6">
        <TaskInput @add-task="addTask" />
        <TaskFilter v-model="filter" />
        <ul class="space-y-3">
          <TransitionGroup name="list">
            <TaskItem
              v-for="task in filteredTasks"
              :key="task.id"
              :task="task"
              @toggle="toggleTask"
              @remove="removeTask"
            />
          </TransitionGroup>
        </ul>
        <div v-if="filteredTasks.length === 0" class="text-center py-12 text-slate-400 text-sm">
          暂无相关任务...
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.list-enter-active, .list-leave-active { transition: all 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28); }
.list-enter-from, .list-leave-to { opacity: 0; transform: translateX(30px); }
</style>
