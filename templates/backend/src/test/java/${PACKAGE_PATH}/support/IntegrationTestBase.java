package ${PACKAGE}.support;

import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MySQLContainer;

/**
 * 集成测试（{@code *IT}）的公共基类：**整个测试 JVM 只起一个 MySQL 容器**。
 *
 * <p>类名刻意不以 {@code Test} 结尾：那样 surefire 也会按命名规则扫到它（虽然抽象类会被跳过），
 * 但名字就已经在暗示「这是单元测试」，是误读的种子。
 *
 * <p>为什么要共享：容器按类启停时，每多一个 {@code *IT} 类就要多起一次 MySQL、
 * 多跑一遍 Flyway，CI 时间随测试类数量线性增长。这里用「静态块启动 + 静态字段持有」
 * 让一个容器服务所有子类；容器在 JVM 退出时由 Testcontainers 的 Ryuk 守护容器回收，
 * 不需要手写关闭。
 *
 * <p><b>不要改回 {@code @Testcontainers} + {@code @Container} 字段</b>——那套注解的语义是
 * 「每个测试类启停一次」，会悄悄抵消这里的共享。子类只继承、不声明容器。
 *
 * <p><b>数据隔离约定</b>：共享库意味着测试之间能互相看见写入的数据，用例**不能假设库是空的**。
 * 写入的数据自己清理，或者用带随机后缀的唯一值（例如 {@code "IT-" + UUID.randomUUID()}）；
 * 断言只看本用例自己写进去的那几行，不要断言「总行数」。
 * 破坏这条约定时，单跑通过、一起跑失败是常见症状。
 */
public abstract class IntegrationTestBase {

    /**
     * 镜像版本与版本表、两份 compose 保持一致；由一致性检查盯着。
     *
     * <p>写 {@code @DynamicPropertySource} 而不是 {@code @ServiceConnection}：后者挂在
     * {@code @Container} 字段上，而那个组合按类启停容器，与这里的共享目标冲突。
     */
    protected static final MySQLContainer<?> MYSQL = new MySQLContainer<>("mysql:8");

    static {
        MYSQL.start();
    }

    @DynamicPropertySource
    static void datasourceProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }
}
