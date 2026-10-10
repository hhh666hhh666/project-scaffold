package ${PACKAGE}.module.example.service;

import org.springframework.stereotype.Service;

@Service
public class ExampleService {

    /**
     * 示例：一条**纯逻辑**，不碰数据库、不拉 Spring 上下文，所以能用纯 JUnit 直接测。
     *
     * <p>写新模块时照这个形状分家：能不依赖容器的逻辑放这里（好测、跑得快），
     * 需要落库的再走 Mapper，并用 `*IT` 那一层去验。
     */
    public String greeting(String name) {
        String trimmed = name == null ? "" : name.trim();
        return trimmed.isEmpty() ? "hello, world" : "hello, " + trimmed;
    }
}
