<template>
  <div>
    <h1>Vue.js + FastAPI</h1>
    <p v-if="loading">Загрузка...</p>
    <p v-else-if="error">{{ error }}</p>
    <p v-else>{{ message }}</p>
    <button @click="fetchData">Обновить</button>
    <p>DB Status: {{ dbStatus }}</p>

    <!-- Добавляем секцию для отображения таблиц -->
    <div class="tables-section">
      <h2>Список таблиц в базе данных</h2>
      <p v-if="loadingTables">Загрузка таблиц...</p>
      <p v-else-if="tablesError">{{ tablesError }}</p>
      <ul v-else-if="tables.length">
        <li v-for="table in tables" :key="table">{{ table }}</li>
      </ul>
      <p v-else>Таблиц не найдено</p>
      <button @click="fetchTables">Обновить список таблиц</button>
    </div>
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
      tables: [],
      loadingTables: false,
      tablesError: null,
    };
  },
  mounted() {
    this.fetchData();
    this.testDb();
    this.fetchTables();
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
    async fetchTables() {
      this.loadingTables = true;
      this.tablesError = null;
      try {
        const response = await axios.get('/api/tables');
        if (response.data.error) {
          this.tablesError = response.data.error;
        } else {
          this.tables = response.data.tables;
        }
      } catch (err) {
        this.tablesError = 'Не удалось загрузить список таблиц: ' + err.message;
      } finally {
        this.loadingTables = false;
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
  margin: 10px;
}
.tables-section {
  margin-top: 30px;
  padding: 20px;
  border-top: 1px solid #ccc;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  margin: 5px 0;
  padding: 5px;
  background-color: #f5f5f5;
  border-radius: 4px;
}
</style>