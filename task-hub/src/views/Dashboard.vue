<script setup>
import TaskHeader from '@/components/TaskHeader.vue'
import TaskInput from '@/components/TaskInput.vue'
import TaskFilter from '@/components/TaskFilter.vue'
import TaskItem from '@/components/TaskItem.vue'
</script>

<template>
  <div class="py-12 px-4">
    <div class="max-w-md mx-auto bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">
      <TaskHeader />
      <main class="p-6">
        <TaskInput />
        <TaskFilter />
        <ul class="space-y-3">
          <TaskItem />
        </ul>
      </main>
    </div>
  </div>
</template>
