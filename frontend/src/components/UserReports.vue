<template>
  <div class="user-reports">
    <h2>Отчеты пользователей</h2>
    
    <!-- Форма для создания отчета -->
    <div class="report-form">
      <div class="form-group">
        <label for="email">Email пользователя</label>
        <input 
          type="email" 
          id="email" 
          v-model="reportForm.email" 
          placeholder="Введите email пользователя"
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
        email: '',
        startDate: '',
        endDate: ''
      },
      reports: [],
      loading: false,
      error: null
    };
  },
  mounted() {
    this.fetchReports();
  },
  methods: {
    async fetchReports() {
      this.loading = true;
      try {
        const response = await axios.get('/api/reports');
        this.reports = response.data;
        this.loading = false;
      } catch (error) {
        console.error('Ошибка при получении отчетов:', error);
        this.error = 'Не удалось загрузить отчеты';
        this.loading = false;
      }
    },
    
    async generateReport() {
      if (!this.reportForm.email || !this.reportForm.startDate || !this.reportForm.endDate) {
        alert('Пожалуйста, заполните все поля формы');
        return;
      }
      
      this.loading = true;
      try {
        const response = await axios.post('/api/reports/generate', {
          email: this.reportForm.email,
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
        link.setAttribute('download', `report_${this.reportForm.email}_${new Date().toISOString().slice(0,10)}.pdf`);
        document.body.appendChild(link);
        link.click();
        
        // Очищаем
        window.URL.revokeObjectURL(url);
        link.remove();
        
        // Сбрасываем форму
        this.reportForm = {
          email: '',
          startDate: '',
          endDate: ''
        };
        
        // Обновляем список отчетов
        await this.fetchReports();
        
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
      
      const date = new Date(dateString);
      return date.toLocaleDateString('ru-RU', { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }).replace(',', '');
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
</style>