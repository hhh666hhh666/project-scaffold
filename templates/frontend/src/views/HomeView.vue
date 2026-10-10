<template>
  <main class="page">
    <h1 class="title">${PROJECT_NAME}</h1>

    <!-- 这行字来自后端 GET /api/example/hello —— 它是「前后端通了」的肉眼判据 -->
    <p class="backend">
      <span class="label">后端返回：</span>
      <span v-if="loading" class="muted">加载中…</span>
      <span v-else-if="error" class="error">{{ error }}</span>
      <span v-else>{{ message }}</span>
    </p>

    <p class="muted">
      脚手架只有这一页。接手后：删掉 example 模块与首页这段调用，从你自己的第一个界面开始。
    </p>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { hello } from '@/api/example'

const message = ref('')
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    message.value = (await hello('world')).message
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败（后端起了吗？）'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page {
  max-width: 42rem;
  margin: 0 auto;
  padding: 4rem 1.5rem;
}
.title {
  margin: 0 0 1rem;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-ink);
}
.backend {
  margin: 0 0 1.5rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-reader);
  color: var(--color-ink);
}
.label {
  color: var(--color-ink-muted);
}
.muted {
  color: var(--color-ink-muted);
}
.error {
  color: var(--color-danger);
}
</style>
