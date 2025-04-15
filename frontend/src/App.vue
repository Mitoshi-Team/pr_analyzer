<template>
  <div id="app">
    <header class="app-header">
      <h1>Система анализа кода АльфаСтрахование</h1>
    </header>
    
    <main class="app-content">
      <UserReports />
    </main>
    
    <footer class="app-footer">
      <!-- Футер без содержимого -->
    </footer>
  </div>
</template>

<script>
import UserReports from './components/UserReports.vue'

export default {
  name: 'App',
  components: {
    UserReports
  }
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  background-color: #f5f5f5;
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-header {
  background-color: #fff;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  text-align: center;
}

.logo {
  height: 60px;
  margin-bottom: 10px;
}

h1 {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
}

.app-content {
  flex: 1;
  padding: 20px;
}

.app-footer {
  padding: 20px;
  margin-top: 20px;
  text-align: center;
}
</style>
