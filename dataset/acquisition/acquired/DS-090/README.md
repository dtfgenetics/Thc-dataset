## 📊 Automated IoT-Based Monitoring of Industrial Hemp in Greenhouses Using Open-Source Systems and Computer Vision

![segmentacion_clasificacion](/img.png)

Carmen Rocamora-Osorio <sup>1,2*</sup>, Fernando Aragon-Rodriguez <sup>1</sup>, Ana María Codes-Alcaraz <sup>2</sup>, Francisco Javier Ferrández-Pastor <sup>3</sup>

<sup>1 Dpto. de Ingeniería, Área Ingeniería Agroforestal, Escuela Politécnica Superior de Orihuela (EPSO), Universidad Miguel Hernández, Ctra. Beniel km. 3,2, 03312, Orihuela (Alicante)</sup>	<br>
<sup>2 Instituto de Investigación e Innovación Agroalimentaria y Agroambiental (CIAGRO), Universidad Miguel Hernández, Ctra. Beniel km. 3,2, 03312, Orihuela (Alicante)</sup>	<br>
<sup>3 Grupo de investigación Informática Industrial y Redes de Computadores (I2RC), Universidad de Alicante, 03690 Alicante</sup>	<br>

### Data repository

Repository of data related to the paper: "Automated IoT-Based Monitoring of Industrial Hemp in Greenhouses Using Open-Source Systems and Computer Vision" (https://doi.org/10.3390/agriengineering7090272).

The **"Hemp_growth"** folder contains hourly images of the monitored plants (C1, C2, C3, C4, and C5) from transplanting until 20 days after transplanting. The **"Hemp_water_stress"** folder contains the train and test data and the trained model for water stress detection. The repository has the following structure:

***Table of contents***

├── 🌱 📁 Hemp_growth<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   ├── 📁 C1<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 ryb_C1_20241212_14_00.jpg<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 ....<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   ├── 📁 C2<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   ├── 📁 C3<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   ├── 📁 C4<br>
│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   └── 📁 C5<br>
├── 💧 📁 Hemp_water_stress<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;       └── 📁 model<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── yolo11x-cls.pt<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    └── 📁 train<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 healthy<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 3 days<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 6 days<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 9 days<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    └── 📁 test<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 healthy<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 3 days<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 6 days<br>
│&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;    │   &nbsp;&nbsp;&nbsp; &nbsp;&nbsp;├── 📁 water stress 9 days<br>


### Abstract

Monitoring the development of greenhouse crops is essential for optimising yield and ensuring the efficient use of resources. A system for monitoring hemp (*Cannabis sativa* L.) cultivation under greenhouse conditions using computer vision has been developed. This system is based on open-source automation software installed on a single-board computer. It integrates various temperature and humidity sensors and surveillance cameras, automating image capture. Hemp seeds of the *Tiborszallasi* variety were sown. After germination plants were transplanted into pots. Five specimens were selected for growth monitoring by image analysis. A surveillance camera was placed in front of each plant. Different approaches were applied to analyse growth during the early stages: two traditional computer vision techniques and a deep learning algorithm. An average growth rate of **2.9 cm/day** was determined and **1.43 mm/°C day**. A mean MAE value of **1.36 cm** was obtained, and the results of the three approaches were very similar. After the first growth stage the plants were subjected to water stress. An algorithm successfully identified healthy and stressed plants, and also detected different stress levels, with an **accuracy of 97%**. These results demonstrate the system's potential to provide objective and quantitative information on plant growth and physiological status.

[**Access to the paper**](https://doi.org/10.3390/agriengineering7090272)
