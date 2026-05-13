"use client";

import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts';
import React, { useEffect, useRef } from 'react';

interface StockChartProps {
  data: any[];
  colors?: {
    backgroundColor?: string;
    lineColor?: string;
    textColor?: string;
    areaTopColor?: string;
    areaBottomColor?: string;
  };
}

export const StockChart = (props: StockChartProps) => {
  const {
    data,
    colors: {
      backgroundColor = 'white',
      lineColor = '#2962FF',
      textColor = 'black',
    } = {},
  } = props;

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      chartRef.current?.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: backgroundColor },
        textColor,
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });
    chartRef.current = chart;

    const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#ef5350',
        downColor: '#26a69a',
        borderVisible: false,
        wickUpColor: '#ef5350',
        wickDownColor: '#26a69a',
    });
    candlestickSeriesRef.current = candlestickSeries;

    const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceScaleId: '', // set as an overlay
    });
    volumeSeriesRef.current = volumeSeries;
    
    volumeSeries.priceScale().applyOptions({
        scaleMargins: {
            top: 0.8, // highest point of the series will be 80% from top
            bottom: 0,
        },
    });

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [backgroundColor, textColor]);

  useEffect(() => {
    if (candlestickSeriesRef.current && data) {
      candlestickSeriesRef.current.setData(data);
      
      const volumeData = data.map(d => ({
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? '#ef5350' : '#26a69a'
      }));
      volumeSeriesRef.current?.setData(volumeData);
      
      chartRef.current?.timeScale().fitContent();
    }
  }, [data]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full h-[400px]"
    />
  );
};
