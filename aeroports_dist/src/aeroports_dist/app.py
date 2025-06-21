import pandas as pd
import numpy as np
import streamlit as st
import folium
from streamlit_folium import st_folium
from math import radians, sin, cos, sqrt, atan2

# Константы для расчета расстояния
EARTH_RADIUS_KM = 6371.0

# Список стран, которые НЕ принимают рейсы из РФ
RESTRICTED_COUNTRIES = [
    # Европа
    "Германия", "Франция", "Италия", "Испания", "Великобритания",
    "Польша", "Чехия", "Словакия", "Венгрия", "Румыния",
    "Болгария", "Греция", "Кипр", "Хорватия", "Словения",
    "Австрия", "Швейцария", "Бельгия", "Нидерланды", "Люксембург",
    "Дания", "Швеция", "Норвегия", "Финляндия", "Исландия",
    "Ирландия", "Португалия", "Мальта", "Эстония", "Латвия", "Литва",
    
    # Северная Америка
    "США", "Канада",
    
    # Азиатско-Тихоокеанский регион
    "Япония", "Южная Корея", "Австралия", "Новая Зеландия",
    "Сингапур", "Малайзия", "Индонезия", "Филиппины",
    
    # Другие
    "Украина", "Молдова"
]

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Вычисляет расстояние между двумя точками на сфере
    используя формулу гаверсинуса.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return EARTH_RADIUS_KM * c

def load_airports_data():
    """Загружает данные об аэропортах из CSV файла."""
    try:
        df = pd.read_csv('datasets/airports.csv', encoding="windows-1251", sep="|")
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return None

def is_russian_airport(airport_row):
    """Проверяет, является ли аэропорт российским."""
    if 'country_rus' in airport_row.index:
        return airport_row['country_rus'] in ['Россия', 'РФ', 'Российская Федерация']
    # Альтернативная проверка по IATA коду
    return str(airport_row.get('iata_code', '')).startswith('U')

def can_fly_between(airport1, airport2, df):
    """
    Проверяет, возможны ли полеты между двумя аэропортами с учетом ограничений.
    """
    # Получаем информацию о странах аэропортов
    country1 = airport1.get('country_rus', '')
    country2 = airport2.get('country_rus', '')
    
    # Проверяем, является ли один из аэропортов российским
    is_russian1 = is_russian_airport(airport1)
    is_russian2 = is_russian_airport(airport2)
    
    # Если оба аэропорта в России - полеты возможны
    if is_russian1 and is_russian2:
        return True
    
    # Если один аэропорт в России, а другой в стране с ограничениями
    if is_russian1 and country2 in RESTRICTED_COUNTRIES:
        return False
    if is_russian2 and country1 in RESTRICTED_COUNTRIES:
        return False
    
    # В остальных случаях полеты возможны
    return True

def find_nearest_airports(df, target_code, n=5):
    """
    Находит n ближайших аэропортов к заданному с учетом ограничений на полеты.
    """
    # Находим целевой аэропорт
    target = df[df['iata_code'] == target_code]
    
    if target.empty:
        return None
    
    target_airport = target.iloc[0]
    target_lat = target_airport['latitude']
    target_lon = target_airport['longitude']
    
    # Исключаем целевой аэропорт из поиска
    other_airports = df[df['iata_code'] != target_code].copy()
    
    # Фильтруем аэропорты с учетом ограничений на полеты
    valid_airports = []
    for idx, airport in other_airports.iterrows():
        if can_fly_between(target_airport, airport, df):
            valid_airports.append(idx)
    
    other_airports = other_airports.loc[valid_airports]
    
    # Вычисляем расстояния
    other_airports['distance_km'] = other_airports.apply(
        lambda row: haversine_distance(
            target_lat, target_lon,
            row['latitude'], row['longitude']
        ),
        axis=1
    )
    
    # Сортируем по расстоянию и берем первые n
    nearest = other_airports.nsmallest(n, 'distance_km')
    
    # Добавляем информацию о стране для отображения
    result_columns = ['iata_code', 'name_eng', 'city_eng', 'latitude', 'longitude', 'distance_km']
    if 'country_rus' in nearest.columns:
        result_columns.append('country_rus')
    
    return nearest[result_columns]

def create_map(target_airport, nearest_airports):
    """
    Создает карту с отображением аэропортов.
    """
    center_lat = target_airport.iloc[0]['latitude']
    center_lon = target_airport.iloc[0]['longitude']
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    
    # Добавляем маркер целевого аэропорта
    target_country = target_airport.iloc[0].get('country_rus', 'Неизвестно')
    folium.Marker(
        [center_lat, center_lon],
        popup=f"{target_airport.iloc[0]['name_eng']} ({target_airport.iloc[0]['iata_code']})\n{target_country}",
        icon=folium.Icon(color='red', icon='plane')
    ).add_to(m)
    
    # Добавляем маркеры ближайших аэропортов
    for _, airport in nearest_airports.iterrows():
        country = airport.get('country_rus', 'Неизвестно')
        folium.Marker(
            [airport['latitude'], airport['longitude']],
            popup=f"{airport['name_eng']} ({airport['iata_code']})\n{country}\nРасстояние: {airport['distance_km']:.1f} км",
            icon=folium.Icon(color='blue', icon='plane')
        ).add_to(m)
        
        # Добавляем линию от целевого аэропорта
        folium.PolyLine(
            [[center_lat, center_lon], [airport['latitude'], airport['longitude']]],
            color='blue',
            weight=2,
            opacity=0.5
        ).add_to(m)
    
    return m

def main():
    st.set_page_config(page_title="Поиск ближайших аэропортов", layout="wide")
    
    st.title("🛫 Поиск ближайших аэропортов")
    st.markdown("Найдите 5 ближайших аэропортов к выбранному с учетом действующих ограничений на полеты")
    
    # Загружаем данные
    with st.spinner("Загрузка данных об аэропортах..."):
        df = load_airports_data()
    
    if df is None:
        st.stop()
    
    # Создаем список аэропортов для выбора
    airport_options = df[['iata_code', 'name_eng']].dropna()
    airport_dict = dict(zip(
        airport_options['iata_code'],
        airport_options['iata_code'] + ' - ' + airport_options['name_eng']
    ))
    
    # Интерфейс выбора аэропорта
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_code = st.selectbox(
            "Выберите аэропорт:",
            options=list(airport_dict.keys()),
            format_func=lambda x: airport_dict[x]
        )
        
        # Показываем информацию о выбранном аэропорте
        selected_airport = df[df['iata_code'] == selected_code].iloc[0]
        if 'country_rus' in selected_airport:
            st.info(f"Страна: {selected_airport['country_rus']}")
            
            # Предупреждение для российских аэропортов
            if is_russian_airport(selected_airport):
                st.warning("⚠️ Для российских аэропортов показаны только доступные направления")
        
        if st.button("Найти ближайшие аэропорты", type="primary"):
            # Находим ближайшие аэропорты
            with st.spinner("Поиск ближайших аэропортов..."):
                nearest = find_nearest_airports(df, selected_code)
            
            if nearest is not None and not nearest.empty:
                st.session_state['nearest_airports'] = nearest
                st.session_state['target_code'] = selected_code
            else:
                st.error("Не найдено доступных аэропортов с учетом ограничений")
    
    # Отображение результатов
    if 'nearest_airports' in st.session_state:
        with col2:
            st.subheader("Ближайшие доступные аэропорты:")
            
            # Форматируем таблицу для отображения
            display_df = st.session_state['nearest_airports'].copy()
            display_df['distance_km'] = display_df['distance_km'].round(1)
            
            # Переименовываем колонки
            rename_dict = {
                'iata_code': 'Код',
                'name_eng': 'Аэропорт',
                'distance_km': 'Расстояние (км)',
                'city_eng': 'Город',
                'country_rus': 'Страна'
            }
            display_df = display_df.rename(columns=rename_dict)
            
            # Выбираем колонки для отображения
            display_columns = ['Код', 'Аэропорт', 'Город', 'Расстояние (км)']
            if 'Страна' in display_df.columns:
                display_columns.insert(2, 'Страна')
            
            st.dataframe(
                display_df[display_columns],
                hide_index=True,
                use_container_width=True
            )
        
        # Отображение карты
        st.subheader("📍 Карта аэропортов")
        
        target_airport = df[df['iata_code'] == st.session_state['target_code']]
        map_obj = create_map(target_airport, st.session_state['nearest_airports'])
        
        st_folium(map_obj, width=None, height=600, returned_objects=[])
        
        # Информация об ограничениях
        with st.expander("ℹ️ Информация об ограничениях на полеты"):
            st.markdown("""
            **Учитываются следующие ограничения:**
            - Из российских аэропортов показаны только направления в страны, с которыми есть авиасообщение
            - Исключены аэропорты стран ЕС, США, Канады и других стран с ограничениями
            - Внутренние рейсы по России доступны без ограничений
            """)

if __name__ == "__main__":
    main()
