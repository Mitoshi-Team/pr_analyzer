<template>
  <div>
    <h1>Vue.js + FastAPI</h1>
    <p v-if="loading">Загрузка...</p>
    <p v-else-if="error">{{ error }}</p>
    <p v-else>{{ message }}</p>
    <button @click="fetchData">Обновить</button>
    <p>DB Status: {{ dbStatus }}</p>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'App',
  data() {
    return {
      message: '',
      dbStatus: '',
      loading: false,
      error: null,
    };
  },
  mounted() {
    this.fetchData();
    this.testDb();
  },
  methods: {
    async fetchData() {
      this.loading = true;
      this.error = null;
      try {
        const response = await axios.get('/api/');
        this.message = response.data.message;
      } catch (err) {
        this.error = 'Не удалось загрузить данные: ' + err.message;
      } finally {
        this.loading = false;
      }
    },
    async testDb() {
      try {
        const response = await axios.get('/api/test-db');
        this.dbStatus = response.data.db_status;
      } catch (err) {
        this.dbStatus = 'Error: ' + err.message;
      }
    },
  },
};
</script>

<style>
div {
  text-align: center;
  margin-top: 50px;
}
button {
  padding: 10px 20px;
  font-size: 16px;
}
</style>