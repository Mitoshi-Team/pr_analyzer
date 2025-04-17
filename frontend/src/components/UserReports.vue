<template>
  <div class="user-reports">
    <h2>Отчеты пользователей</h2>
    
    <!-- Форма для создания отчета -->
    <div class="report-form">
      <div class="form-group">
        <label for="repoLinks">Ссылки на репозитории</label>
        <div class="repo-input-container">
          <input 
            type="text" 
            id="repoLink" 
            v-model="newRepoLink" 
            placeholder="https://github.com/owner/repo"
            class="form-control"
            @keyup.enter="addRepoLink"
          >
          <button @click="addRepoLink" class="add-repo-btn">Добавить</button>
        </div>
        <div class="repo-links-list" v-if="reportForm.repoLinks.length > 0">
          <div v-for="(link, index) in reportForm.repoLinks" :key="index" class="repo-link-item">
            <span>{{ link }}</span>
            <button @click="removeRepoLink(index)" class="remove-link-btn">×</button>
          </div>
        </div>
      </div>
      
      <div class="form-group">
        <label for="login">Логин пользователя</label>
        <input 
          type="text" 
          id="login" 
          v-model="reportForm.login" 
          placeholder="Введите логин пользователя"
          class="form-control"
        >
      </div>
      
      <div class="form-row">
        <div class="form-group date-group">
          <label for="startDate">Дата начала</label>
          <input 
            type="date" 
            id="startDate" 
            v-model="reportForm.startDate"
            class="form-control"
          >
        </div>
        
        <div class="form-group date-group">
          <label for="endDate">Дата окончания</label>
          <input 
            type="date" 
            id="endDate" 
            v-model="reportForm.endDate"
            class="form-control"
          >
        </div>
      </div>
      
      <button @click="generateReport" class="generate-btn" :disabled="loading">
        {{ loading ? 'Формирование...' : 'Сформировать отчет' }}
      </button>
    </div>
    
    <!-- История отчетов -->
    <div class="reports-history">
      <h3 style="margin-left: 16px;">История отчетов</h3>
      <div class="table-container">
        <table class="reports-table">
          <thead>
            <tr>
              <th>Email пользователя</th>
              <th>Файл</th>
              <th>Дата создания</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(report, index) in reports" :key="report.id || index">
              <td>{{ report.email }}</td>
              <td>
                <button @click="downloadReport(report.id)" class="download-btn">
                  Скачать
                </button>
              </td>
              <td>{{ formatDate(report.created_at) }}</td>
            </tr>
            <tr v-if="reports.length === 0">
              <td colspan="3" class="no-data">Нет доступных отчетов</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'UserReports',
  data() {
    return {
      reportForm: {
        login: '',
        repoLinks: [],
        startDate: '',
        endDate: ''
      },
      newRepoLink: '',
      reports: [],
      loading: false,
      error: null
    };
  },
  mounted() {
    this.fetchReports();
  },
  methods: {
    addRepoLink() {
      if (this.newRepoLink && this.newRepoLink.trim()) {
        if (!this.reportForm.repoLinks.includes(this.newRepoLink.trim())) {
          this.reportForm.repoLinks.push(this.newRepoLink.trim());
        }
        this.newRepoLink = '';
      }
    },
    removeRepoLink(index) {
      this.reportForm.repoLinks.splice(index, 1);
    },
    
    async fetchReports() {
      this.loading = true;
      try {
        console.log("Запрашиваем список отчетов");
        const response = await axios.get('/api/reports');
        console.log("Получены отчеты:", response.data);
        this.reports = response.data;
      } catch (error) {
        console.error('Ошибка при получении отчетов:', error);
        this.error = 'Не удалось загрузить отчеты';
      } finally {
        this.loading = false;
      }
    },
    
    async generateReport() {
      if (!this.reportForm.login || !this.reportForm.startDate || !this.reportForm.endDate || this.reportForm.repoLinks.length === 0) {
        alert('Пожалуйста, заполните все поля формы и добавьте хотя бы одну ссылку на репозиторий');
        return;
      }
      
      this.loading = true;
      try {
        console.log("Отправка запроса на генерацию отчета", this.reportForm);
        const response = await axios.post('/api/reports/generate', {
          email: this.reportForm.login, // оставляем поле email для обратной совместимости
          login: this.reportForm.login,
          repoLinks: this.reportForm.repoLinks,
          startDate: this.reportForm.startDate,
          endDate: this.reportForm.endDate
        }, {
          responseType: 'blob' // Указываем, что ожидаем бинарные данные
        });
        
        // Создаем объект Blob из ответа
        const blob = new Blob([response.data], { type: 'application/pdf' });
        
        // Создаем ссылку для скачивания
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `report_${this.reportForm.login}_${new Date().toISOString().slice(0,10)}.pdf`);
        document.body.appendChild(link);
        link.click();
        
        // Очищаем
        window.URL.revokeObjectURL(url);
        link.remove();
        
        // Сбрасываем форму
        this.reportForm = {
          login: '',
          repoLinks: [],
          startDate: '',
          endDate: ''
        };
        this.newRepoLink = '';
        
        // Небольшая задержка перед обновлением списка отчетов,
        // чтобы дать время базе данных завершить транзакцию
        console.log("Ожидаем завершения операции в БД...");
        setTimeout(async () => {
          console.log("Обновляем список отчетов после генерации");
          await this.fetchReports();
        }, 1000);
        
      } catch (error) {
        console.error('Ошибка при формировании отчета:', error);
        alert('Не удалось сформировать отчет');
      } finally {
        this.loading = false;
      }
    },
    
    async downloadReport(reportId) {
      try {
        const response = await axios.get(`/api/reports/${reportId}/download`, {
          responseType: 'blob'
        });
        
        // Создаем объект Blob из ответа
        const blob = new Blob([response.data], { type: 'application/pdf' });
        
        // Создаем ссылку для скачивания
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        const fileName = `report_${new Date().toISOString().slice(0, 10)}.pdf`;
        link.setAttribute('download', fileName);
        document.body.appendChild(link);
        link.click();
        
        // Очищаем
        window.URL.revokeObjectURL(url);
        link.remove();
      } catch (error) {
        console.error('Ошибка при скачивании отчета:', error);
        alert('Не удалось скачать отчет');
      }
    },
    
    formatDate(dateString) {
      if (!dateString) return '—';
      
      try {
        // Преобразуем строку даты в объект Date
        const date = new Date(dateString);
        
        if (isNaN(date.getTime())) {
          console.error('Невалидная дата:', dateString);
          return '—';
        }
        
        // Добавляем смещение для московского времени (+3 часа от UTC)
        // Сначала получаем timestamp в миллисекундах
        const utcTime = date.getTime();
        
        // Создаем новую дату с поправкой на московское время (+3 часа)
        const mskTime = new Date(utcTime);
        
        // Форматируем дату с использованием локали ru-RU
        const formattedDate = new Intl.DateTimeFormat('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        }).format(mskTime);
        
        // Добавляем метку МСК для понятности
        return `${formattedDate} (МСК)`;
      } catch (error) {
        console.error('Ошибка форматирования даты:', error, dateString);
        return dateString || '—';
      }
    }
  }
};
</script>

<style scoped>
.user-reports {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

h2 {
  margin-bottom: 20px;
  color: #333;
  font-weight: 500;
}

h3 {
  margin: 25px 0 15px;
  color: #444;
  font-weight: 500;
}

.report-form {
  background-color: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 30px;
}

.form-group {
  margin-bottom: 15px;
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  flex-wrap: wrap; /* Добавляем перенос элементов, если не хватает места */
}

.date-group {
  flex: 1;
  min-width: 140px; /* Устанавливаем минимальную ширину */
  max-width: calc(50% - 10px); /* Ограничиваем максимальную ширину */
}

label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  text-align: left;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box; /* Учитываем отступы в общей ширине */
}

.generate-btn {
  display: block;
  width: 100%;
  padding: 12px;
  background-color: #1e88e5;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
}

.generate-btn:hover {
  background-color: #1976d2;
}

.generate-btn:disabled {
  background-color: #90caf9;
  cursor: not-allowed;
}

.reports-history {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.table-container {
  overflow-x: auto;
}

.reports-table {
  width: 100%;
  border-collapse: collapse;
}

.reports-table th,
.reports-table td {
  padding: 12px 15px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.reports-table th {
  background-color: #f8f9fa;
  font-weight: 500;
}

.reports-table tr:last-child td {
  border-bottom: none;
}

.download-btn {
  background-color: #1e88e5;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.download-btn:hover {
  background-color: #1976d2;
}

.no-data {
  text-align: center;
  color: #888;
  padding: 30px 0;
}

.repo-input-container {
  display: flex;
  gap: 10px;
}

.add-repo-btn {
  padding: 10px 15px;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}

.add-repo-btn:hover {
  background-color: #45a049;
}

.repo-links-list {
  margin-top: 10px;
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 5px;
}

.repo-link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background-color: #f5f5f5;
  margin-bottom: 5px;
  border-radius: 4px;
}

.remove-link-btn {
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-link-btn:hover {
  background-color: #d32f2f;
}
</style>