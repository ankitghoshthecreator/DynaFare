package com.dynafare.api.service;

import com.dynafare.api.dto.PriceUpdateEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaConsumerService {

    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    private static final String PRICE_UPDATES_TOPIC = "price-updates";

    @KafkaListener(topics = PRICE_UPDATES_TOPIC, groupId = "api-service")
    public void consumePriceUpdate(String message) {
        try {
            PriceUpdateEvent event = objectMapper.readValue(message, PriceUpdateEvent.class);
            log.info("Received price update for zone {}: new surge multiplier = {}", 
                     event.getZoneId(), event.getNewSurgeMultiplier());
            
            // Store the latest surge multiplier in Redis for the zone.
            // In Part 9, this will also broadcast via WebSocket to active clients in this zone.
            String redisKey = "zone:" + event.getZoneId() + ":surge_multiplier";
            redisTemplate.opsForValue().set(redisKey, String.valueOf(event.getNewSurgeMultiplier()));
            
        } catch (JsonProcessingException e) {
            log.error("Failed to deserialize PriceUpdateEvent", e);
        }
    }
}
