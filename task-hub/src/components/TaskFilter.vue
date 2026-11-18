<script setup>
const filters = ['all', 'active', 'completed']
</script>

<template>
  <div class="flex p-1 bg-slate-100 rounded-xl mb-6">
    <button
      v-for="f in filters"
      :key="f"
      class="flex-1 py-1.5 text-xs font-bold rounded-lg capitalize text-slate-500"
    >
      {{ f }}
    </button>
  </div>
</template>
